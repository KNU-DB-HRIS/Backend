from calendar import monthrange
from datetime import date, timedelta

from flask import Blueprint, g, request
from sqlalchemy.exc import SQLAlchemyError

from app.db import all_rows, page_query, scalar, today, transaction
from app.errors import ApiError
from app.modules.approvals.services import APPROVAL_JOINS
from app.modules.employees.services import employed, employment_rows
from app.security import require_auth
from app.validation import iso_date, page_result, pagination, query_choice

bp = Blueprint("dashboard", __name__)

CATEGORY_SQL = (
    "CASE a.resource_type WHEN 'employee' THEN '직원 관리' WHEN 'approval' THEN '인사 관리' "
    "WHEN 'payroll_statement' THEN '급여 관리' ELSE '기타' END"
)
ACTIVITY_FROM = (
    "FROM audit_logs a LEFT JOIN users u ON u.user_id=a.user_id "
    "LEFT JOIN employees e ON e.employee_id=u.employee_id "
    "WHERE COALESCE(a.company_id,e.company_id)=:company"
)


def members(conn):
    rows = employment_rows(conn)
    day = today()
    previous = day.replace(day=1) - timedelta(days=1)
    total = sum(employed(row, day) for row in rows)
    last_total = sum(employed(row, previous) for row in rows)
    return {
        "total": total,
        "active": sum(employed(row, day) and row["employment_status"] == "ACTIVE" for row in rows),
        "change_rate_vs_last_month": round((total - last_total) / last_total, 4)
        if last_total
        else None,
    }


class Unavailable(Exception):
    def __init__(self, reason):
        self.reason = reason


def attendance_today(conn):
    day = today()
    if day.weekday() >= 5:
        raise Unavailable("NON_WORKDAY")
    employees = employment_rows(conn)
    active = {
        row["employee_id"]
        for row in employees
        if employed(row, day) and row["employment_status"] == "ACTIVE"
    }
    records = all_rows(
        conn,
        "SELECT a.employee_id,a.status FROM attendance_records a "
        "JOIN employees e ON e.employee_id=a.employee_id WHERE e.company_id=:company AND a.work_date=:day",
        {"company": g.actor["company_id"], "day": day},
    )
    records = [record for record in records if record["employee_id"] in active]
    if not records:
        raise Unavailable("NO_DATA")
    total = sum(employed(row, day) for row in employees)
    present = sum(row["status"] == "PRESENT" for row in records)
    return {
        "present": present,
        "members_total": total,
        "present_ratio_of_members": round(present / total, 4) if total else None,
        "on_leave": sum(row["status"] == "LEAVE" for row in records),
        "absent": sum(row["status"] == "ABSENT" for row in records),
        "not_checked_in": len(active) - len(records),
    }


def monthly_headcount(conn):
    employees = employment_rows(conn)
    day = today()
    result = []
    for offset in range(5, -1, -1):
        index = day.year * 12 + day.month - 1 - offset
        year, month = index // 12, index % 12 + 1
        end = day if offset == 0 else date(year, month, monthrange(year, month)[1])
        result.append(
            {
                "month": f"{year:04d}-{month:02d}",
                "headcount": sum(employed(row, end) for row in employees),
            }
        )
    return {
        "items": result,
        "current": result[-1]["headcount"],
        "period_change": result[-1]["headcount"] - result[0]["headcount"],
    }


def event_rows(conn, start, end=None, limit=None):
    sql = (
        "SELECT event_id,title,start_at,end_at,all_day,location,target FROM hr_events "
        "WHERE company_id=:company AND start_at>=:start"
    )
    if end:
        sql += " AND start_at<:end"
    sql += " ORDER BY start_at,event_id"
    if limit:
        sql += " LIMIT :limit"
    rows = all_rows(
        conn, sql, {"company": g.actor["company_id"], "start": start, "end": end, "limit": limit}
    )
    for row in rows:
        row["all_day"] = bool(row["all_day"])
    return rows


def upcoming(conn):
    rows = event_rows(conn, today(), limit=3)
    for row in rows:
        row.pop("end_at")
    return rows


def recent(conn):
    return all_rows(
        conn,
        "SELECT a.action_type AS action," + CATEGORY_SQL + " AS category,COUNT(*) AS count,"
        "MAX(a.created_at) AS latest_at "
        + ACTIVITY_FROM
        + " GROUP BY DATE(a.created_at),a.action_type,a.resource_type ORDER BY latest_at DESC,action LIMIT 3",
        {"company": g.actor["company_id"]},
    )


def month_summary(conn):
    day = today()
    start = day.replace(day=1)
    rows = employment_rows(conn)
    data = {
        "new_hires": sum(start <= row["hire_date"] <= day for row in rows),
        "transfers": scalar(
            conn,
            "SELECT COUNT(*) FROM assignment_history h JOIN employees e ON e.employee_id=h.employee_id "
            "WHERE e.company_id=:company AND h.action_type='TRANSFER' "
            "AND COALESCE(h.effective_date,h.action_date) BETWEEN :start AND :end",
            {"company": g.actor["company_id"], "start": start, "end": day},
        ),
        "attendance_rate": None,
        "attendance_missing_records": None,
        "attendance_status": "SOURCE_ERROR",
    }
    try:
        records = all_rows(
            conn,
            "SELECT a.employee_id,a.work_date,a.status FROM attendance_records a "
            "JOIN employees e ON e.employee_id=a.employee_id WHERE e.company_id=:company "
            "AND a.work_date>=:start AND a.work_date<:end",
            {"company": g.actor["company_id"], "start": start, "end": day},
        )
        record_map = {(row["employee_id"], row["work_date"]): row["status"] for row in records}
        missing = present = absent = expected = 0
        current = start
        while current < day:
            if current.weekday() < 5:
                for employee in rows:
                    if employee["employment_status"] != "ACTIVE" or not employed(employee, current):
                        continue
                    expected += 1
                    value = record_map.get((employee["employee_id"], current))
                    missing += value is None
                    present += value == "PRESENT"
                    absent += value == "ABSENT"
            current += timedelta(days=1)
        data["attendance_missing_records"] = missing
        data["attendance_status"] = (
            "INCOMPLETE" if missing else "OK" if expected and present + absent else "NO_DATA"
        )
        if not missing and present + absent:
            data["attendance_rate"] = present / (present + absent)
    except SQLAlchemyError:
        pass
    return data


def widget(function):
    try:
        with transaction() as conn:
            data = function(conn)
        return {"status": "ok", "reason": None, "data": data}
    except Unavailable as error:
        return {"status": "unavailable", "reason": error.reason, "data": None}
    except SQLAlchemyError:
        return {"status": "unavailable", "reason": "SOURCE_ERROR", "data": None}


@bp.get("/dashboard")
@require_auth(admin=True)
def dashboard():
    if request.args:
        raise ApiError("VALIDATION_ERROR", details={"field": "query"})
    functions = {
        "members": members,
        "attendance_today": attendance_today,
        "pending_approvals": lambda conn: {
            "count": scalar(
                conn,
                f"SELECT COUNT(*) {APPROVAL_JOINS} WHERE e.company_id=:company AND a.status='IN_PROGRESS'",
                {"company": g.actor["company_id"]},
            )
        },
        "monthly_headcount": monthly_headcount,
        "upcoming_events": upcoming,
        "recent_activities": recent,
        "month_summary": month_summary,
    }
    return {
        "date": today(),
        "widgets": {key: widget(function) for key, function in functions.items()},
    }


@bp.get("/events")
@require_auth(admin=True)
def events():
    page, size = pagination()
    start = iso_date(request.args.get("from", today().isoformat()), "from")
    end = iso_date(request.args.get("to", (start + timedelta(days=30)).isoformat()), "to")
    if start > end:
        raise ApiError("INVALID_RANGE")
    if (end - start).days >= 366 or end == date.max:
        raise ApiError("VALIDATION_ERROR", details={"field": "to"})
    with transaction() as conn:
        result = page_result(event_rows(conn, start, end + timedelta(days=1)), page, size)
    return {"from": start, "to": end, **result}


@bp.get("/activities")
@require_auth(admin=True)
def activities():
    page, size = pagination()
    category = query_choice("category", ("직원 관리", "인사 관리", "급여 관리", "기타"))
    condition = ACTIVITY_FROM + (f" AND ({CATEGORY_SQL})=:category" if category else "")
    params = {
        "company": g.actor["company_id"],
        "category": category,
    }
    with transaction() as conn:
        return page_query(
            conn,
            "a.audit_log_id AS audit_id,a.action_type AS action,"
            + CATEGORY_SQL
            + " AS category,a.resource_type,a.resource_id,e.employee_name AS actor_name,a.created_at AS at",
            condition,
            params,
            "a.created_at DESC,a.audit_log_id DESC",
            page,
            size,
        )
