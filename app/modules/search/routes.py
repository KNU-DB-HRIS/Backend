from flask import Blueprint, g

from app.db import all_rows, scalar, transaction
from app.modules.approvals.services import APPROVAL_JOINS, visible_condition
from app.modules.employees.services import EMPLOYEE_JOINS
from app.security import is_admin, require_auth
from app.validation import like, query_int, query_text

bp = Blueprint("search", __name__)


@bp.get("/search")
@require_auth()
def search():
    q, limit = query_text(required=True), query_int("limit", 5, 100)
    params = {
        "q": like(q),
        "limit": limit,
        "company": g.actor["company_id"],
        "actor": g.actor["user_id"],
    }
    employees = {"items": [], "total": 0}
    with transaction() as conn:
        if is_admin():
            condition = (
                f"{EMPLOYEE_JOINS} WHERE e.company_id=:company AND "
                "(e.employee_name LIKE :q ESCAPE '!' OR e.employee_no LIKE :q ESCAPE '!' "
                "OR d.department_name LIKE :q ESCAPE '!')"
            )
            employees["total"] = scalar(conn, "SELECT COUNT(*) " + condition, params)
            employees["items"] = all_rows(
                conn,
                "SELECT e.employee_id,e.employee_no,e.employee_name AS name,"
                "d.department_name,p.position_name,e.employment_status "
                + condition
                + " ORDER BY e.employee_no,e.employee_id LIMIT :limit",
                params,
            )
        else:
            # 사원: 사내 주소록 수준(DB 뷰 vw_employee_directory). 이름 또는 부서로 찾고, 재직·휴직자만, 연락처·상태는 주지 않음
            condition = (
                "FROM vw_employee_directory v WHERE v.company_id=:company "
                "AND v.employment_status IN ('ACTIVE','ON_LEAVE') "
                "AND (v.employee_name LIKE :q ESCAPE '!' OR v.department_name LIKE :q ESCAPE '!')"
            )
            employees["total"] = scalar(conn, "SELECT COUNT(*) " + condition, params)
            employees["items"] = all_rows(
                conn,
                "SELECT v.employee_id,v.employee_no,v.employee_name AS name,v.department_name,v.position_name "
                + condition
                + " ORDER BY v.employee_name,v.employee_id LIMIT :limit",
                params,
            )
        condition = (
            f"{APPROVAL_JOINS} WHERE e.company_id=:company "
            "AND a.title LIKE :q ESCAPE '!' AND " + visible_condition()
        )
        total = scalar(conn, "SELECT COUNT(*) " + condition, params)
        rows = all_rows(
            conn,
            "SELECT a.approval_request_id AS request_id,a.title,a.status,DATE(a.requested_at) AS requested_at "
            + condition
            + " ORDER BY a.requested_at DESC,a.approval_request_id DESC LIMIT :limit",
            params,
        )
    return {"q": q, "employees": employees, "approvals": {"items": rows, "total": total}}
