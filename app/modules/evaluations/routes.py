from datetime import timedelta

from flask import Blueprint, g

from app.db import all_rows, one, today, transaction
from app.errors import ApiError
from app.security import require_auth
from app.validation import page_result, pagination, query_choice, query_text

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


@bp.get("/evaluation-periods")
@require_auth(admin=True)
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
@require_auth(admin=True)
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
@require_auth(admin=True)
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
