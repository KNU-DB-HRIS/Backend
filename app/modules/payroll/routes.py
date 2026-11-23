from flask import Blueprint, g, request

from app.db import all_rows, audit, insert, one, page_query, today, transaction, update
from app.errors import ApiError
from app.modules.employees.services import EMPLOYEE_JOINS, employee_filter, employee_row
from app.security import require_auth, scope_employee
from app.validation import body, date_field, int_field, iso_date, pagination, text_field

bp = Blueprint("payroll", __name__)

COMPONENTS = "components_status,base_salary,position_allowance,meal_allowance,other_allowance"
COMPONENT_KEYS = ("base_salary", "position_allowance", "meal_allowance", "other_allowance")
# 현재 급여 = 적용일이 오늘 이전인 최신 행 (변경 등록은 오늘 이전 적용일만 받지만, 이력에 미래 행이 있어도 미리 반영되지 않게)
CURRENT = "effective_date<=CURDATE()"


@bp.get("/salaries")
@require_auth(admin=True)
def listing():
    page, size = pagination()
    condition, params = employee_filter()
    with transaction() as conn:
        return page_query(
            conn,
            "e.employee_id,e.employee_no,e.employee_name AS name,d.department_name,"
            "p.position_name,e.employment_status,(SELECT h.new_salary FROM salary_history h "
            "WHERE h.employee_id=e.employee_id AND h." + CURRENT + " "
            "ORDER BY h.effective_date DESC,h.salary_history_id DESC LIMIT 1) "
            "AS current_salary",
            f"{EMPLOYEE_JOINS} WHERE {condition}",
            params,
            "e.employee_no,e.employee_id",
            page,
            size,
        )


@bp.get("/employees/<int:employee_id>/salary")
@require_auth()
def current_salary(employee_id):
    scope_employee(employee_id)
    with transaction() as conn:
        employee_row(conn, employee_id)
        result = one(
            conn,
            f"SELECT employee_id,effective_date,new_salary AS total,{COMPONENTS} "
            f"FROM salary_history WHERE employee_id=:id AND {CURRENT} "
            "ORDER BY effective_date DESC,salary_history_id DESC LIMIT 1",
            {"id": employee_id},
        )
        if not result:
            raise ApiError("SALARY_NOT_SET", 404)
        return result


@bp.get("/employees/<int:employee_id>/salary-history")
@require_auth()
def history(employee_id):
    scope_employee(employee_id)
    with transaction() as conn:
        employee = employee_row(conn, employee_id)
        start = iso_date(request.args.get("from", employee["hire_date"].isoformat()), "from")
        end = iso_date(request.args.get("to", today().isoformat()), "to")
        if start > end:
            raise ApiError("INVALID_RANGE")
        rows = all_rows(
            conn,
            "SELECT salary_history_id,effective_date,previous_salary,new_salary,"
            f"new_salary-previous_salary AS change_amount,reason,{COMPONENTS} "
            "FROM salary_history WHERE employee_id=:id AND effective_date BETWEEN :start AND :end "
            "ORDER BY effective_date,salary_history_id",
            {"id": employee_id, "start": start, "end": end},
        )
    return {"employee_id": employee_id, "from": start, "to": end, "items": rows}


@bp.post("/employees/<int:employee_id>/salary-history")
@require_auth(admin=True)
def change_salary(employee_id):
    """SAL-04 급여 변경 등록. 총액은 받지 않고 네 항목 합으로 계산(항상 COMPLETE).
    적용일은 기존 최신 적용일보다 뒤 + 오늘 이전(sp_change_salary와 같은 규칙: 미래 예약은 범위 제외).
    등록 즉시 현재 급여가 되므로 employees.current_salary(vw_current_salaries)와 이력이 항상 같음"""
    money = int_field(0, 100000000)
    data = body(
        {
            "effective_date": date_field(),
            **{key: money for key in COMPONENT_KEYS},
            "reason": text_field(200),
        },
        ("effective_date", *COMPONENT_KEYS, "reason"),
    )
    effective = data["effective_date"]
    with transaction() as conn:
        employee = employee_row(conn, employee_id, lock=True)
        if employee["employment_status"] == "TERMINATED":
            raise ApiError("EMPLOYEE_TERMINATED", 409)
        if effective < employee["hire_date"]:
            raise ApiError("EFFECTIVE_BEFORE_HIRE")
        if effective > today():
            raise ApiError("FUTURE_DATE_NOT_SUPPORTED")
        last = one(
            conn,
            f"SELECT new_salary,effective_date,{COMPONENTS} FROM salary_history WHERE employee_id=:id "
            "ORDER BY effective_date DESC,salary_history_id DESC LIMIT 1 FOR UPDATE",
            {"id": employee_id},
        )
        if last:
            if effective == last["effective_date"]:
                raise ApiError("EFFECTIVE_DATE_TAKEN", 409)
            if effective < last["effective_date"]:
                raise ApiError("EFFECTIVE_DATE_NOT_LATEST", 409)
            if last["components_status"] == "COMPLETE" and all(
                int(last[key]) == data[key] for key in COMPONENT_KEYS
            ):
                raise ApiError("NO_CHANGE")
        total = sum(data[key] for key in COMPONENT_KEYS)
        previous = int(last["new_salary"]) if last else None
        identifier = insert(
            conn,
            "salary_history",
            {
                "employee_id": employee_id,
                "previous_salary": previous,
                "new_salary": total,
                "effective_date": effective,
                "reason": data["reason"],
                "changed_by_user_id": g.actor["user_id"],
                **{key: data[key] for key in COMPONENT_KEYS},
                "components_status": "COMPLETE",
            },
        )
        update(conn, "employees", "employee_id", employee_id, {"current_salary": total})
        audit(conn, "SALARY_CHANGED", "salary_history", identifier)
    return {
        "salary_history_id": identifier,
        "employee_id": employee_id,
        "effective_date": effective,
        "previous_salary": previous,
        "new_salary": total,
        "change_amount": None if previous is None else total - previous,
        "components_status": "COMPLETE",
        "reason": data["reason"],
        "is_current": True,
        **{key: data[key] for key in COMPONENT_KEYS},
    }, 201
