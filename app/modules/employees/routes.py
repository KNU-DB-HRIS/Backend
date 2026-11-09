import secrets

from flask import Blueprint, g
from sqlalchemy.exc import IntegrityError

from app.db import (
    audit,
    execute,
    insert,
    lock_company,
    one,
    page_query,
    scalar,
    today,
    transaction,
    update,
)
from app.errors import ApiError
from app.modules.employees.services import (
    ASSIGNMENT_FIELDS,
    EMPLOYEE_JOINS,
    assignments,
    employee_detail,
    employee_filter,
    employee_row,
)
from app.modules.organization.services import validate_reference
from app.security import create_account, require_auth, scope_employee
from app.validation import (
    body,
    boolean,
    choice_field,
    date_field,
    email,
    int_field,
    page_result,
    pagination,
    query_choice,
    text_field,
)

bp = Blueprint("employees", __name__)

EMPLOYMENT_TYPES = ("FULL_TIME", "CONTRACT", "INTERN")
ORG_COLUMNS = {
    "department_id": "departments",
    "position_id": "positions",
    "job_id": "jobs",
    "job_title_id": "job_titles",
}
DERIVED = ("department_name", "position_name", "job_name", "job_title_name")
CREATE_FIELDS = {
    "name": text_field(50),
    "email": email,
    "phone": text_field(20),
    "department_id": int_field(),
    "position_id": int_field(),
    "job_id": int_field(),
    "job_title_id": int_field(nullable=True),
    "hire_date": date_field(),
    "employment_type": choice_field(*EMPLOYMENT_TYPES),
    "birth_date": date_field(True),
    "grant_access": boolean,
    "username": text_field(50, True),
}


@bp.get("/employees")
@require_auth(admin=True)
def listing():
    page, size = pagination()
    condition, params = employee_filter()
    sort = query_choice("sort", ("hire_date", "-hire_date", "name", "employee_no"), "employee_no")
    ordering = {
        "hire_date": "e.hire_date",
        "-hire_date": "e.hire_date DESC",
        "name": "e.employee_name",
        "employee_no": "e.employee_no",
    }[sort]
    with transaction() as conn:
        return page_query(
            conn,
            "e.employee_id,e.employee_no,e.employee_name AS name,e.department_id,"
            "d.department_name,e.position_id,p.position_name,e.employment_status,e.hire_date",
            f"{EMPLOYEE_JOINS} WHERE {condition}",
            params,
            f"{ordering},e.employee_id",
            page,
            size,
        )


@bp.get("/employees/<int:employee_id>")
@require_auth()
def detail(employee_id):
    scope_employee(employee_id)
    with transaction() as conn:
        return employee_detail(conn, employee_id)


@bp.post("/employees")
@require_auth(admin=True)
def create_employee():
    data = body(
        CREATE_FIELDS,
        (
            "name",
            "email",
            "phone",
            "department_id",
            "position_id",
            "job_id",
            "hire_date",
            "employment_type",
        ),
        readonly=DERIVED,
    )
    grant = data.pop("grant_access", False)
    username = data.pop("username", None)
    if grant and not username:
        raise ApiError("VALIDATION_ERROR", details={"field": "username"})
    temporary = None
    with transaction() as conn:
        lock_company(conn, g.actor["company_id"])
        for key, table in ORG_COLUMNS.items():
            validate_reference(conn, table, key, data.get(key))
        if scalar(
            conn, "SELECT COUNT(*) FROM employees WHERE email=:email", {"email": data["email"]}
        ):
            raise ApiError("EMAIL_DUPLICATE", 409)
        if grant and scalar(
            conn, "SELECT COUNT(*) FROM users WHERE username=:name", {"name": username}
        ):
            raise ApiError("USERNAME_DUPLICATE", 409)
        sequence = scalar(
            conn,
            "SELECT COALESCE(MAX(CAST(SUBSTRING(employee_no,4) AS UNSIGNED)),0)+1 "
            "FROM employees WHERE company_id=:company AND employee_no REGEXP '^EMP[0-9]+$'",
            {"company": g.actor["company_id"]},
        )
        data["employee_name"] = data.pop("name")
        data.update(
            employee_no=f"EMP{int(sequence):03d}",
            company_id=g.actor["company_id"],
            employment_status="ACTIVE",
        )
        try:
            employee_id = insert(conn, "employees", data)
        except IntegrityError:
            raise ApiError("EMAIL_DUPLICATE", 409) from None
        insert(
            conn,
            "assignment_history",
            {
                "employee_id": employee_id,
                "action_type": "HIRE",
                "action_date": today(),
                "effective_date": data["hire_date"],
                "reason": "직원 등록",
                "created_by_user_id": g.actor["user_id"],
                **{f"to_{key}": data.get(key) for key in ORG_COLUMNS},
            },
        )
        if grant:
            role = one(conn, "SELECT role_id FROM roles WHERE role_code='EMPLOYEE' AND is_active=1")
            if not role:
                raise ApiError("REFERENCE_INVALID", details={"field": "EMPLOYEE role"})
            temporary = secrets.token_urlsafe(18)
            try:
                create_account(conn, employee_id, username, temporary, role["role_id"])
            except IntegrityError:
                raise ApiError("USERNAME_DUPLICATE", 409) from None
        audit(conn, "EMPLOYEE_CREATED", "employee", employee_id)
        details = employee_detail(conn, employee_id)
        keys = (
            "employee_id",
            "employee_no",
            "name",
            "department_id",
            "department_name",
            "position_id",
            "position_name",
            "employment_status",
            "hire_date",
            "account",
        )
        result = {key: details[key] for key in keys}
        result["temporary_password"] = temporary
    return result, 201


@bp.patch("/employees/<int:employee_id>")
@require_auth(admin=True)
def edit_employee(employee_id):
    fields = {
        key: CREATE_FIELDS[key]
        for key in ("name", "email", "phone", "birth_date", "employment_type")
    }
    fields.update(address=text_field(200, True), education=text_field(50, True))
    data = body(fields, readonly=DERIVED)
    with transaction() as conn:
        lock_company(conn, g.actor["company_id"])
        employee_row(conn, employee_id, True)
        if "name" in data:
            data["employee_name"] = data.pop("name")
        try:
            update(conn, "employees", "employee_id", employee_id, data)
        except IntegrityError:
            raise ApiError("EMAIL_DUPLICATE", 409) from None
        audit(conn, "EMPLOYEE_UPDATED", "employee", employee_id)
        return employee_detail(conn, employee_id)


@bp.get("/employees/<int:employee_id>/assignments")
@require_auth(admin=True)
def history(employee_id):
    page, size = pagination()
    with transaction() as conn:
        employee_row(conn, employee_id)
        return page_result(assignments(conn, employee_id), page, size)


@bp.post("/employees/<int:employee_id>/assignments")
@require_auth(admin=True)
def assign(employee_id):
    fields = {
        "action_type": text_field(20),
        "effective_date": date_field(),
        "reason": text_field(300),
        "document_url": text_field(500, True),
        **{f"to_{key}": int_field(nullable=key == "job_title_id") for key in ORG_COLUMNS},
    }
    data = body(fields, ("action_type", "effective_date", "reason"))
    action = data["action_type"]
    kinds = {
        "TRANSFER": "department_id",
        "PROMOTION": "position_id",
        "JOB_CHANGE": "job_id",
        "TITLE_CHANGE": "job_title_id",
    }
    if action == "TERMINATION":
        raise ApiError("USE_TERMINATION_ENDPOINT")
    if action not in {*kinds, "REASSIGNMENT"}:
        raise ApiError("VALIDATION_ERROR", details={"field": "action_type"})
    with transaction() as conn:
        lock_company(conn, g.actor["company_id"])
        employee = employee_row(conn, employee_id, True)
        if employee["employment_status"] == "TERMINATED":
            raise ApiError("EMPLOYEE_TERMINATED", 409)
        if data["effective_date"] > today():
            raise ApiError("FUTURE_DATE_NOT_SUPPORTED")
        if data["effective_date"] < employee["hire_date"]:
            raise ApiError("EFFECTIVE_BEFORE_HIRE")
        targets = {key: data.get(f"to_{key}", employee[key]) for key in ORG_COLUMNS}
        for key, table in ORG_COLUMNS.items():
            validate_reference(conn, table, key, targets[key])
        changed = {key for key in ORG_COLUMNS if targets[key] != employee[key]}
        if not changed:
            raise ApiError("NO_CHANGE")
        if action in kinds and kinds[action] not in changed:
            raise ApiError("ACTION_TYPE_MISMATCH")
        if "department_id" in changed and scalar(
            conn,
            "SELECT COUNT(*) FROM departments WHERE manager_employee_id=:id",
            {"id": employee_id},
        ):
            raise ApiError("MANAGER_REASSIGN_REQUIRED", 409)
        assignment_id = insert(
            conn,
            "assignment_history",
            {
                **data,
                "employee_id": employee_id,
                "action_date": today(),
                "created_by_user_id": g.actor["user_id"],
                **{f"from_{key}": employee[key] for key in ORG_COLUMNS},
                **{f"to_{key}": value for key, value in targets.items()},
            },
        )
        update(conn, "employees", "employee_id", employee_id, targets)
        audit(conn, "EMPLOYEE_ASSIGNED", "employee", employee_id)
        assignment = one(
            conn,
            f"SELECT {ASSIGNMENT_FIELDS} FROM vw_assignment_timeline "
            "WHERE assignment_history_id=:id",
            {"id": assignment_id},
        )
        return {"assignment": assignment, "employee": {"employee_id": employee_id, **targets}}, 201


@bp.post("/employees/<int:employee_id>/termination")
@require_auth(admin=True)
def terminate(employee_id):
    data = body(
        {"termination_date": date_field(), "reason": text_field(300)},
        ("termination_date", "reason"),
    )
    if employee_id == g.actor["employee_id"]:
        raise ApiError("CANNOT_TERMINATE_SELF", 409)
    with transaction() as conn:
        lock_company(conn, g.actor["company_id"])
        employee = employee_row(conn, employee_id, True)
        if employee["employment_status"] == "TERMINATED":
            raise ApiError("ALREADY_TERMINATED", 409)
        if scalar(
            conn,
            "SELECT COUNT(*) FROM departments WHERE manager_employee_id=:id",
            {"id": employee_id},
        ):
            raise ApiError("MANAGER_REASSIGN_REQUIRED", 409)
        if data["termination_date"] > today():
            raise ApiError("FUTURE_DATE_NOT_SUPPORTED")
        if data["termination_date"] < employee["hire_date"]:
            raise ApiError("TERMINATION_BEFORE_HIRE")
        update(
            conn,
            "employees",
            "employee_id",
            employee_id,
            {"employment_status": "TERMINATED", "termination_date": data["termination_date"]},
        )
        account_count = scalar(
            conn, "SELECT COUNT(*) FROM users WHERE employee_id=:id", {"id": employee_id}
        )
        execute(
            conn, "UPDATE users SET status='DISABLED' WHERE employee_id=:id", {"id": employee_id}
        )
        execute(
            conn,
            "UPDATE auth_sessions s JOIN users u ON u.user_id=s.user_id SET revoked_at=NOW(6) "
            "WHERE u.employee_id=:id",
            {"id": employee_id},
        )
        insert(
            conn,
            "assignment_history",
            {
                "employee_id": employee_id,
                "action_type": "TERMINATION",
                "action_date": today(),
                "effective_date": data["termination_date"],
                "reason": data["reason"],
                "created_by_user_id": g.actor["user_id"],
                **{f"from_{key}": employee[key] for key in ORG_COLUMNS},
                **{f"to_{key}": employee[key] for key in ORG_COLUMNS},
            },
        )
        audit(conn, "EMPLOYEE_TERMINATED", "employee", employee_id)
    return {
        "employee_id": employee_id,
        "employment_status": "TERMINATED",
        "termination_date": data["termination_date"],
        "account_status": "DISABLED" if account_count else None,
    }


@bp.delete("/employees/<int:employee_id>")
@require_auth(admin=True)
def delete_employee(employee_id):
    if employee_id == g.actor["employee_id"]:
        raise ApiError("CANNOT_DELETE_SELF", 409)
    with transaction() as conn:
        lock_company(conn, g.actor["company_id"])
        employee_row(conn, employee_id, True)
        params = {"id": employee_id}
        if scalar(conn, "SELECT COUNT(*) FROM departments WHERE manager_employee_id=:id", params):
            raise ApiError("MANAGER_REASSIGN_REQUIRED", 409)
        checks = [
            "SELECT COUNT(*) FROM assignment_history WHERE employee_id=:id AND action_type<>'HIRE'",
            "SELECT COUNT(*) FROM salary_history WHERE employee_id=:id",
            "SELECT COUNT(*) FROM employee_evaluations WHERE employee_id=:id OR evaluator_employee_id=:id",
            "SELECT COUNT(*) FROM evaluation_stage_records WHERE evaluator_id=:id",
            "SELECT COUNT(*) FROM documents WHERE employee_id=:id",
            "SELECT COUNT(*) FROM payroll_statements WHERE employee_id=:id",
            "SELECT COUNT(*) FROM attendance_records WHERE employee_id=:id",
            "SELECT COUNT(*) FROM users WHERE employee_id=:id AND last_login_at IS NOT NULL",
            "SELECT COUNT(*) FROM audit_logs WHERE user_id IN (SELECT user_id FROM users WHERE employee_id=:id)",
            "SELECT COUNT(*) FROM audit_logs WHERE resource_type IN ('employee','employees') AND resource_id=:id "
            "AND action_type NOT IN ('INSERT','EMPLOYEE_CREATED')",
            "SELECT COUNT(*) FROM approval_requests WHERE requester_user_id IN (SELECT user_id FROM users WHERE employee_id=:id)",
            "SELECT COUNT(*) FROM approval_steps WHERE approver_user_id IN (SELECT user_id FROM users WHERE employee_id=:id)",
        ]
        if any(scalar(conn, sql, params) for sql in checks):
            raise ApiError("EMPLOYEE_HAS_HISTORY", 409)
        try:
            execute(
                conn,
                "DELETE FROM user_roles WHERE user_id IN (SELECT user_id FROM users WHERE employee_id=:id)",
                params,
            )
            execute(conn, "DELETE FROM users WHERE employee_id=:id", params)
            execute(conn, "DELETE FROM assignment_history WHERE employee_id=:id", params)
            execute(conn, "DELETE FROM employees WHERE employee_id=:id", params)
        except IntegrityError:
            raise ApiError("EMPLOYEE_HAS_HISTORY", 409) from None
        audit(conn, "EMPLOYEE_DELETED", "employee", employee_id)
    return "", 204
