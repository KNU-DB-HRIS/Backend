from calendar import monthrange
from datetime import date, timedelta

from flask import Blueprint, g, request
from sqlalchemy.exc import SQLAlchemyError

from app.db import all_rows, scalar, today, transaction
from app.errors import ApiError
from app.modules.approvals.services import APPROVAL_JOINS
from app.modules.employees.services import employed, employment_rows
from app.modules.schedule.services import attach_targets
from app.security import require_auth
from app.validation import iso_date, page_result, pagination

bp = Blueprint("dashboard", __name__)

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
        "SELECT event_id,title,description,start_at,end_at,all_day,location,scope,target,created_at,updated_at FROM hr_events "
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
@require_auth(permission="DASHBOARD_COMPANY")
def dashboard():
    if request.args:
        raise ApiError("VALIDATION_ERROR", details={"field": "query"})
    functions = {
        "members": members,
        "pending_approvals": lambda conn: {
            "count": scalar(
                conn,
                f"SELECT COUNT(*) {APPROVAL_JOINS} WHERE e.company_id=:company AND a.status='IN_PROGRESS'",
                {"company": g.actor["company_id"]},
            )
        },
        "monthly_headcount": monthly_headcount,
        "upcoming_events": upcoming,
    }
    return {
        "date": today(),
        "widgets": {key: widget(function) for key, function in functions.items()},
    }


@bp.get("/events")
@require_auth(permission="EVENT_MANAGE")
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
        attach_targets(conn, result["items"])
    return {"from": start, "to": end, **result}


