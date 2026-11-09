from flask import g

from app.db import all_rows, one
from app.errors import ApiError
from app.validation import like, query_choice, query_int, query_text

EMPLOYEE_FIELDS = (
    "e.employee_id,e.employee_no,e.employee_name AS name,e.employment_status,"
    "e.employment_type,e.department_id,d.department_name,e.position_id,p.position_name,"
    "e.job_id,j.job_name,e.job_title_id,t.job_title_name,e.email,e.phone,e.birth_date,"
    "e.hire_date,e.termination_date,e.address,e.education"
)
EMPLOYEE_JOINS = (
    "FROM employees e JOIN departments d ON d.department_id=e.department_id "
    "JOIN positions p ON p.position_id=e.position_id JOIN jobs j ON j.job_id=e.job_id "
    "LEFT JOIN job_titles t ON t.job_title_id=e.job_title_id"
)
ASSIGNMENT_FIELDS = (
    "assignment_history_id AS assignment_id,action_type,"
    "COALESCE(effective_date,action_date) AS effective_date,reason,"
    "from_department_name,to_department_name,from_position_name,to_position_name,"
    "from_job_name,to_job_name,from_job_title_name,to_job_title_name"
)


def employee_row(conn, identifier, lock=False):
    row = one(
        conn,
        "SELECT * FROM employees WHERE employee_id=:id AND company_id=:company"
        + (" FOR UPDATE" if lock else ""),
        {"id": identifier, "company": g.actor["company_id"]},
    )
    if not row:
        raise ApiError("EMPLOYEE_NOT_FOUND", 404)
    return row


def assignments(conn, identifier, limit=None):
    return all_rows(
        conn,
        f"SELECT {ASSIGNMENT_FIELDS} FROM vw_assignment_timeline "
        "WHERE employee_id=:id ORDER BY COALESCE(effective_date,action_date) DESC,assignment_history_id DESC"
        + (" LIMIT :limit" if limit is not None else ""),
        {"id": identifier, "limit": limit},
    )


def employee_detail(conn, identifier):
    row = employee_profile(conn, identifier)
    row["account"] = one(
        conn,
        "SELECT user_id,username,status FROM users WHERE employee_id=:id ORDER BY user_id LIMIT 1",
        {"id": identifier},
    )
    row["recent_assignments"] = assignments(conn, identifier, 3)
    return row


def employee_profile(conn, identifier):
    row = one(
        conn,
        f"SELECT {EMPLOYEE_FIELDS} {EMPLOYEE_JOINS} WHERE e.employee_id=:id AND e.company_id=:company",
        {"id": identifier, "company": g.actor["company_id"]},
    )
    if not row:
        raise ApiError("EMPLOYEE_NOT_FOUND", 404)
    return row


def employment_rows(conn):
    if "employment_rows" not in g:
        g.employment_rows = all_rows(
            conn,
            "SELECT employee_id,department_id,hire_date,termination_date,employment_status "
            "FROM employees WHERE company_id=:company",
            {"company": g.actor["company_id"]},
        )
    return g.employment_rows


def employed(row, day):
    return row["hire_date"] <= day and (
        row["termination_date"] is None or day < row["termination_date"]
    )


def employee_filter():
    conditions, params = ["e.company_id=:company"], {"company": g.actor["company_id"]}
    q = query_text()
    department = query_int("department_id")
    status = query_choice("employment_status", ("ACTIVE", "ON_LEAVE", "TERMINATED"))
    if q:
        conditions.append(
            "(e.employee_name LIKE :q ESCAPE '!' OR e.employee_no LIKE :q ESCAPE '!' "
            "OR d.department_name LIKE :q ESCAPE '!')"
        )
        params["q"] = like(q)
    if department:
        conditions.append("e.department_id=:department")
        params["department"] = department
    if status:
        conditions.append("e.employment_status=:status")
        params["status"] = status
    return " AND ".join(conditions), params
