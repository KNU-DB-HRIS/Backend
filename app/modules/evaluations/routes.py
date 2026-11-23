from datetime import timedelta

from flask import Blueprint, g

from app.db import all_rows, audit, insert, now, one, today, transaction, update
from app.errors import ApiError
from app.security import require_auth
from app.validation import (
    body,
    choice_field,
    int_field,
    invalid,
    page_result,
    pagination,
    query_choice,
    query_text,
    text_field,
)

bp = Blueprint("evaluations", __name__)

STAGES = ("GOAL", "SELF", "PEER", "LEADER")
GRADES = ("S", "A", "B", "C", "D")


def period_dto(row):
    result = {
        "period_id": row["evaluation_period_id"],
        "year": row["evaluation_year"],
        "half": row["evaluation_half"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "status": row["status"],
        "days_left": (row["end_date"] - today()).days if row["status"] == "IN_PROGRESS" else None,
    }
    half = "상반기" if result["half"] == "H1" else "하반기"
    result["title"] = f"{result['year']} {half} 성과 평가"
    return result


def evaluation_data(conn, period_id):
    period = one(
        conn,
        "SELECT p.* FROM evaluation_periods p WHERE p.evaluation_period_id=:id "
        "AND p.company_id=:company",
        {"id": period_id, "company": g.actor["company_id"]},
    )
    if not period:
        raise ApiError("PERIOD_NOT_FOUND", 404)
    targets = all_rows(
        conn,
        "SELECT v.employee_evaluation_id AS evaluation_id,v.employee_id,v.grade,"
        "e.employee_name AS name,d.department_name FROM employee_evaluations v "
        "JOIN employees e ON e.employee_id=v.employee_id JOIN departments d ON d.department_id=e.department_id "
        "WHERE v.evaluation_period_id=:id AND e.company_id=:company ORDER BY e.employee_no,e.employee_id",
        {"id": period_id, "company": g.actor["company_id"]},
    )
    records = all_rows(
        conn,
        "SELECT r.evaluation_id,r.stage,r.submitted_at FROM evaluation_stage_records r "
        "JOIN employee_evaluations v ON v.employee_evaluation_id=r.evaluation_id "
        "JOIN employees e ON e.employee_id=v.employee_id WHERE v.evaluation_period_id=:id AND e.company_id=:company",
        {"id": period_id, "company": g.actor["company_id"]},
    )
    return period, targets, records


# ---------- 단계 평가 제출 (EVAL-04)과 내가 할 평가 (EVAL-05) ----------
# 누가: GOAL, SELF = 대상자 본인 / PEER = 대상자와 같은 부서의 재직 동료(대상자, 리더 제외, 여러 명) /
#       LEADER = employee_evaluations.evaluator_employee_id. 인사관리자 대리 제출 없음
# 순서: SELF는 GOAL 뒤, PEER는 SELF 뒤이고 LEADER 전, LEADER는 동료 평가 1건 이상 뒤
EVALUATION_SOURCE = (
    "FROM employee_evaluations v JOIN employees e ON e.employee_id=v.employee_id "
    "JOIN departments d ON d.department_id=e.department_id "
    "JOIN evaluation_periods p ON p.evaluation_period_id=v.evaluation_period_id "
)
EVALUATION_FIELDS = (
    "v.employee_evaluation_id AS evaluation_id,v.employee_id,v.evaluator_employee_id,"
    "e.employee_name AS name,e.department_id,d.department_name,p.evaluation_period_id,"
    "p.evaluation_year,p.evaluation_half,p.start_date,p.end_date,p.status AS period_status"
)


def me_row(conn):
    return one(
        conn,
        "SELECT employee_id,department_id,employment_status FROM employees WHERE employee_id=:id",
        {"id": g.actor["employee_id"]},
    )


def my_stages(evaluation, me):
    """이 평가에서 내가 낼 수 있는 단계"""
    if evaluation["employee_id"] == me["employee_id"]:
        return {"GOAL", "SELF"}
    if evaluation["evaluator_employee_id"] == me["employee_id"]:
        return {"LEADER"}
    if evaluation["department_id"] == me["department_id"] and me["employment_status"] == "ACTIVE":
        return {"PEER"}
    return set()


def order_ok(stage, done):
    return {
        "GOAL": True,
        "SELF": "GOAL" in done,
        "PEER": "SELF" in done and "LEADER" not in done,
        "LEADER": "PEER" in done,
    }[stage]


def progress(done):
    return next((s for s in STAGES if s not in done), "COMPLETED"), len(done & set(STAGES)) / 4


def period_open(row):
    return row["period_status"] == "IN_PROGRESS" and row["start_date"] <= today() <= row["end_date"]


def period_title(row):
    return f"{row['evaluation_year']} {'상반기' if row['evaluation_half'] == 'H1' else '하반기'} 성과 평가"


@bp.post("/evaluations/<int:evaluation_id>/stage-records")
@require_auth()
def submit_stage(evaluation_id):
    """EVAL-04 단계 평가 제출. GOAL은 목표 내용(comment) 필수, 점수 없음. 나머지는 점수 0~100 필수"""
    data = body(
        {"stage": choice_field(*STAGES), "score": int_field(0, 100, True), "comment": text_field(500, True)},
        ("stage",),
    )
    stage, score, comment = data["stage"], data.get("score"), data.get("comment")
    if stage == "GOAL":
        if score is not None:
            invalid("score")
        if not comment:
            invalid("comment")
    elif score is None:
        invalid("score")
    with transaction() as conn:
        evaluation = one(
            conn,
            f"SELECT {EVALUATION_FIELDS} {EVALUATION_SOURCE} "
            "WHERE v.employee_evaluation_id=:id AND p.company_id=:company FOR UPDATE",
            {"id": evaluation_id, "company": g.actor["home_company_id"]},
        )
        if not evaluation:
            raise ApiError("EVALUATION_NOT_FOUND", 404)
        if not period_open(evaluation):
            raise ApiError("PERIOD_CLOSED", 409)
        me = me_row(conn)
        if stage not in my_stages(evaluation, me):
            raise ApiError("NOT_STAGE_EVALUATOR", 403)
        records = all_rows(
            conn,
            "SELECT stage,evaluator_id FROM evaluation_stage_records WHERE evaluation_id=:id FOR UPDATE",
            {"id": evaluation_id},
        )
        done = {row["stage"] for row in records}
        mine = any(row["stage"] == stage and row["evaluator_id"] == me["employee_id"] for row in records)
        if mine or (stage != "PEER" and stage in done):
            raise ApiError("STAGE_ALREADY_SUBMITTED", 409)
        if not order_ok(stage, done):
            raise ApiError("STAGE_ORDER", 409)
        submitted_at = now()
        record_id = insert(
            conn,
            "evaluation_stage_records",
            {
                "evaluation_id": evaluation_id,
                "stage": stage,
                "evaluator_id": me["employee_id"],
                "score": score,
                "comment": comment,
                "submitted_at": submitted_at,
            },
        )
        current, rate = progress(done | {stage})
        if current == "COMPLETED":
            # 4단계가 모두 차면 완료. 최종 등급(grade) 산식은 미정(P8)이라 그대로 둠
            update(
                conn,
                "employee_evaluations",
                "employee_evaluation_id",
                evaluation_id,
                {"status": "COMPLETED", "evaluated_at": submitted_at},
            )
        audit(conn, "EVALUATION_STAGE_SUBMITTED", "evaluation", evaluation_id)
    return {
        "stage_record_id": record_id,
        "evaluation_id": evaluation_id,
        "stage": stage,
        "evaluator_employee_id": me["employee_id"],
        "score": score,
        "comment": comment,
        "submitted_at": submitted_at,
        "current_stage": current,
        "progress_rate": rate,
    }, 201


@bp.get("/me/evaluation-tasks")
@require_auth()
def my_tasks():
    """EVAL-05 내가 할 평가: 진행 중인 회차(기간 안)에서 지금 낼 수 있는 단계 + 내가 낸 평가"""
    with transaction() as conn:
        me = me_row(conn)
        rows = all_rows(
            conn,
            f"SELECT {EVALUATION_FIELDS} {EVALUATION_SOURCE} "
            "WHERE p.company_id=:company AND p.status='IN_PROGRESS' AND :today BETWEEN p.start_date AND p.end_date "
            "AND (v.employee_id=:me OR v.evaluator_employee_id=:me OR e.department_id=:department) "
            "ORDER BY p.end_date,e.employee_name,v.employee_evaluation_id",
            {
                "company": g.actor["home_company_id"],
                "today": today(),
                "me": me["employee_id"],
                "department": me["department_id"],
            },
        )
        records = {row["evaluation_id"]: [] for row in rows}
        if records:
            params = {f"id_{i}": value for i, value in enumerate(records)}
            for record in all_rows(
                conn,
                "SELECT evaluation_id,stage,evaluator_id,score,comment,submitted_at FROM evaluation_stage_records "
                f"WHERE evaluation_id IN ({','.join(':' + k for k in params)})",
                params,
            ):
                records[record["evaluation_id"]].append(record)
    tasks, submitted = [], []
    for row in rows:
        done = {r["stage"] for r in records[row["evaluation_id"]]}
        mine = [r for r in records[row["evaluation_id"]] if r["evaluator_id"] == me["employee_id"]]
        target = {"employee_id": row["employee_id"], "name": row["name"], "department_name": row["department_name"]}
        base = {
            "evaluation_id": row["evaluation_id"],
            "period_title": period_title(row),
            "end_date": row["end_date"],
            "target": target,
        }
        for stage in STAGES:
            already = any(r["stage"] == stage for r in mine) or (stage != "PEER" and stage in done)
            if stage in my_stages(row, me) and not already and order_ok(stage, done):
                tasks.append({**base, "stage": stage, "days_left": (row["end_date"] - today()).days})
        for record in mine:
            submitted.append(
                {
                    **base,
                    "stage": record["stage"],
                    "score": record["score"],
                    "comment": record["comment"],
                    "submitted_at": record["submitted_at"],
                }
            )
    submitted.sort(key=lambda x: x["submitted_at"], reverse=True)
    return {"items": tasks, "total": len(tasks), "submitted": submitted}


@bp.get("/evaluation-periods")
@require_auth(permission="EVALUATION_READ")
def periods():
    with transaction() as conn:
        rows = all_rows(
            conn,
            "SELECT p.*,COUNT(e.employee_id) AS target_count FROM evaluation_periods p "
            "LEFT JOIN employee_evaluations v ON v.evaluation_period_id=p.evaluation_period_id "
            "LEFT JOIN employees e ON e.employee_id=v.employee_id AND e.company_id=p.company_id "
            "WHERE p.company_id=:company "
            "GROUP BY p.evaluation_period_id ORDER BY p.start_date DESC,p.evaluation_period_id DESC",
            {"company": g.actor["company_id"]},
        )
    items = [{**period_dto(row), "target_count": row["target_count"]} for row in rows]
    return {"items": items, "total": len(items)}


@bp.get("/evaluation-periods/<int:period_id>/summary")
@require_auth(permission="EVALUATION_READ")
def summary(period_id):
    with transaction() as conn:
        period, targets, records = evaluation_data(conn, period_id)
    completed = {row["evaluation_id"]: set() for row in targets}
    previous = {key: set() for key in completed}
    for record in records:
        completed[record["evaluation_id"]].add(record["stage"])
        if record["submitted_at"].date() <= today() - timedelta(days=7):
            previous[record["evaluation_id"]].add(record["stage"])
    count = len(targets)
    total_done = sum(len(value) for value in completed.values())
    last_done = sum(len(value) for value in previous.values())
    graded = sum(row["grade"] in GRADES for row in targets)
    return {
        **period_dto(period),
        "target_count": count,
        "completed_count": sum(len(value) == 4 for value in completed.values()),
        "not_submitted_count": sum(not value for value in completed.values()),
        "progress_rate": total_done / (count * 4) if count else None,
        "progress_rate_change_vs_last_week": (total_done - last_done) / (count * 4)
        if count
        else None,
        "stages": [
            {
                "stage": stage,
                "completed_targets": sum(stage in v for v in completed.values()),
                "rate": sum(stage in v for v in completed.values()) / count if count else None,
            }
            for stage in STAGES
        ],
        "grade_distribution": [
            {
                "grade": grade,
                "count": sum(row["grade"] == grade for row in targets),
                "rate": sum(row["grade"] == grade for row in targets) / graded if graded else None,
            }
            for grade in GRADES
        ],
    }


@bp.get("/evaluation-periods/<int:period_id>/participants")
@require_auth(permission="EVALUATION_READ")
def participants(period_id):
    page, size = pagination()
    q = query_text()
    status = query_choice("status", ("NOT_STARTED", *STAGES, "COMPLETED"))
    grade = query_choice("grade", GRADES)
    with transaction() as conn:
        _, targets, records = evaluation_data(conn, period_id)
    done = {row["evaluation_id"]: set() for row in targets}
    for record in records:
        done[record["evaluation_id"]].add(record["stage"])
    for target in targets:
        stages = done[target["evaluation_id"]]
        target["progress_rate"] = len(stages) / 4
        target["status"] = (
            "NOT_STARTED"
            if not stages
            else next((s for s in STAGES if s not in stages), "COMPLETED")
        )
    targets = [
        row
        for row in targets
        if (
            not q
            or q.casefold() in row["name"].casefold()
            or q.casefold() in row["department_name"].casefold()
        )
        and (not status or row["status"] == status)
        and (not grade or row["grade"] == grade)
    ]
    return page_result(targets, page, size)
