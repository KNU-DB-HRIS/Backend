"""일정 관리: 등록, 수정, 삭제(HR_ADMIN), 표시 대상 인원 미리보기, 내 일정(로그인 사용자)

목록 GET /events 는 대시보드 모듈(DASH-02)에 있고 같은 대상 정보를 붙여서 돌려준다.
"""
from datetime import datetime, timedelta

from flask import Blueprint, g, request

from app.db import KST, all_rows, audit, execute, insert, one, today, transaction, update
from app.errors import ApiError
from app.modules.schedule.services import (
    attach_targets,
    audience_count,
    company_departments,
    department_chain,
    target_label,
)
from app.security import require_auth
from app.validation import body, boolean, enum, invalid, iso_date, page_result, pagination, string

bp = Blueprint("schedule", __name__)

MAX_TARGETS = 20
EVENT_SELECT = (
    "SELECT e.event_id,e.title,e.description,e.start_at,e.end_at,e.all_day,e.location,e.scope,e.target,"
    "e.created_at,e.updated_at FROM hr_events e"
)


def datetime_field(nullable=False):
    def parse(value, field):
        if value is None and nullable:
            return None
        if not isinstance(value, str) or len(value) > 32:
            invalid(field)
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            invalid(field)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(KST).replace(tzinfo=None)
        return parsed.replace(second=0, microsecond=0)

    return parse


def targets_field(value, field):
    if not isinstance(value, list) or len(value) > MAX_TARGETS:
        invalid(field)
    merged = {}
    for item in value:
        if not isinstance(item, dict) or set(item) - {"department_id", "include_children"}:
            invalid(field)
        department = item.get("department_id")
        include = item.get("include_children", True)
        if isinstance(department, bool) or not isinstance(department, int) or department < 1 or not isinstance(include, bool):
            invalid(field)
        merged[department] = merged.get(department, False) or include
    return [{"department_id": k, "include_children": v} for k, v in merged.items()]


FIELDS = {
    "title": lambda v, k: string(v, k, 100),
    "description": lambda v, k: string(v, k, 1000, nullable=True),
    "start_at": datetime_field(),
    "end_at": datetime_field(nullable=True),
    "all_day": boolean,
    "location": lambda v, k: string(v, k, 100, nullable=True),
    "scope": lambda v, k: enum(v, k, ("COMPANY", "DEPARTMENTS")),
    "targets": targets_field,
}


def checked_targets(conn, scope, targets):
    if scope == "COMPANY":
        if targets:
            invalid("targets")
        return []
    if not targets:
        invalid("targets")
    departments = {d["department_id"]: d for d in company_departments(conn)}
    for t in targets:
        department = departments.get(t["department_id"])
        if not department:
            raise ApiError("REFERENCE_INVALID", details={"field": "targets"})
        if not department["is_active"]:
            invalid("targets")
    return targets


def write_targets(conn, event_id, targets):
    execute(conn, "DELETE FROM hr_event_departments WHERE event_id=:id", {"id": event_id})
    for t in targets:
        insert(conn, "hr_event_departments", {
            "event_id": event_id, "company_id": g.actor["company_id"],
            "department_id": t["department_id"], "include_children": t["include_children"],
        })


def load_event(conn, event_id, lock=False):
    row = one(
        conn,
        EVENT_SELECT + " WHERE e.event_id=:id AND e.company_id=:company" + (" FOR UPDATE" if lock else ""),
        {"id": event_id, "company": g.actor["company_id"]},
    )
    if not row:
        raise ApiError("NOT_FOUND", 404)
    return row


def detail(conn, event_id):
    row = attach_targets(conn, [load_event(conn, event_id)])[0]
    row["audience_count"] = audience_count(conn, row["scope"], row["targets"])
    return row


def refresh_label(conn, event_id, scope):
    targets = attach_targets(conn, [{"event_id": event_id, "scope": scope}])[0]["targets"]
    update(conn, "hr_events", "event_id", event_id, {"target": target_label(scope, targets)})


def check_range(start, end):
    if end is not None and end < start:
        raise ApiError("INVALID_RANGE")


@bp.post("/events")
@require_auth(permission="EVENT_MANAGE")
def create_event():
    data = body(FIELDS, required=("title", "start_at"))
    scope = data.pop("scope", "COMPANY")
    targets = data.pop("targets", [])
    check_range(data["start_at"], data.get("end_at"))
    with transaction() as conn:
        targets = checked_targets(conn, scope, targets)
        event_id = insert(conn, "hr_events", {
            "company_id": g.actor["company_id"], "title": data["title"], "description": data.get("description"),
            "start_at": data["start_at"], "end_at": data.get("end_at"), "all_day": data.get("all_day", False),
            "location": data.get("location"), "scope": scope, "created_by_user_id": g.actor["user_id"],
        })
        write_targets(conn, event_id, targets)
        refresh_label(conn, event_id, scope)
        audit(conn, "EVENT_CREATED", "event", event_id)
        return detail(conn, event_id), 201


@bp.patch("/events/<int:event_id>")
@require_auth(permission="EVENT_MANAGE")
def edit_event(event_id):
    data = body(FIELDS)
    with transaction() as conn:
        current = attach_targets(conn, [load_event(conn, event_id, lock=True)])[0]
        check_range(data.get("start_at", current["start_at"]), data.get("end_at", current["end_at"]))
        changes = {k: data[k] for k in ("title", "description", "start_at", "end_at", "all_day", "location") if k in data}
        scope = current["scope"]
        # 대상: scope나 targets를 보내면 전체 교체, 보내지 않으면 그대로
        if "scope" in data or "targets" in data:
            scope = data.get("scope", current["scope"])
            targets = data.get("targets")
            if targets is None:
                targets = [] if scope == "COMPANY" else [
                    {"department_id": t["department_id"], "include_children": t["include_children"]} for t in current["targets"]
                ]
            targets = checked_targets(conn, scope, targets)
            changes["scope"] = scope
            write_targets(conn, event_id, targets)
        if changes:
            update(conn, "hr_events", "event_id", event_id, changes)
        refresh_label(conn, event_id, scope)
        audit(conn, "EVENT_UPDATED", "event", event_id)
        return detail(conn, event_id)


@bp.delete("/events/<int:event_id>")
@require_auth(permission="EVENT_MANAGE")
def delete_event(event_id):
    with transaction() as conn:
        load_event(conn, event_id, lock=True)
        execute(conn, "DELETE FROM hr_events WHERE event_id=:id AND company_id=:company",
                {"id": event_id, "company": g.actor["company_id"]})
        audit(conn, "EVENT_DELETED", "event", event_id)
    return "", 204


@bp.get("/events/audience")
@require_auth(permission="EVENT_MANAGE")
def event_audience():
    """등록, 수정 폼의 '표시 대상 재직자 N명'. targets=부서ID:하위포함(1|0) 쉼표 구분, 예: 3:1,7:0"""
    scope = request.args.get("scope", "DEPARTMENTS")
    if scope not in ("COMPANY", "DEPARTMENTS"):
        invalid("scope")
    targets = []
    for part in filter(None, request.args.get("targets", "").split(",")):
        department, _, include = part.partition(":")
        if not department.isdigit() or include not in ("", "0", "1"):
            invalid("targets")
        targets.append({"department_id": int(department), "include_children": include != "0"})
    if len(targets) > MAX_TARGETS:
        invalid("targets")
    with transaction() as conn:
        if scope == "DEPARTMENTS":
            known = {d["department_id"] for d in company_departments(conn)}
            targets = [t for t in targets if t["department_id"] in known]
        return {"scope": scope, "audience_count": audience_count(conn, scope, targets)}


@bp.get("/me/events")
@require_auth()
def my_events():
    """내 일정: 소속 회사의 전사 일정 + 내 부서나 (하위 포함으로 지정된) 상위 부서가 대상인 일정"""
    page, size = pagination(50)
    start = iso_date(request.args.get("from", today().isoformat()), "from")
    end = iso_date(request.args.get("to", (start + timedelta(days=30)).isoformat()), "to")
    if start > end:
        raise ApiError("INVALID_RANGE")
    if (end - start).days >= 366:
        invalid("to")
    company = g.actor["home_company_id"]
    with transaction() as conn:
        mine = one(conn, "SELECT department_id FROM employees WHERE employee_id=:id", {"id": g.actor["employee_id"]})
        chain = department_chain(conn, company, mine["department_id"]) if mine else []
        own = chain[0] if chain else 0
        ancestors = ",".join(str(int(x)) for x in chain[1:]) or "0"
        rows = all_rows(
            conn,
            EVENT_SELECT + " WHERE e.company_id=:company AND e.start_at>=:start AND e.start_at<:end AND ("
            "e.scope='COMPANY' OR EXISTS (SELECT 1 FROM hr_event_departments t WHERE t.event_id=e.event_id AND "
            f"(t.department_id=:own OR (t.include_children=1 AND t.department_id IN ({ancestors}))))) "
            "ORDER BY e.start_at,e.event_id",
            {"company": company, "start": start, "end": end + timedelta(days=1), "own": own},
        )
        result = page_result(rows, page, size)
        attach_targets(conn, result["items"])
    return {"from": start, "to": end, **result}
