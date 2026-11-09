from flask import Blueprint, request

from app.db import all_rows, one, page_query, today, transaction
from app.errors import ApiError
from app.modules.employees.services import EMPLOYEE_JOINS, employee_filter, employee_row
from app.security import require_auth, scope_employee
from app.validation import iso_date, pagination

bp = Blueprint("payroll", __name__)

COMPONENTS = "components_status,base_salary,position_allowance,meal_allowance,other_allowance"


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
            "WHERE h.employee_id=e.employee_id ORDER BY h.effective_date DESC,h.salary_history_id DESC LIMIT 1) "
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
            "FROM salary_history WHERE employee_id=:id ORDER BY effective_date DESC,salary_history_id DESC LIMIT 1",
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
