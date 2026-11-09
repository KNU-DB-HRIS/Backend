from flask import g

from app.db import all_rows, one, scalar
from app.errors import ApiError
from app.security import is_admin

APPROVAL_JOINS = (
    "FROM approval_requests a JOIN users u ON u.user_id=a.requester_user_id "
    "JOIN employees e ON e.employee_id=u.employee_id "
    "JOIN departments d ON d.department_id=e.department_id"
)


def visible_condition(alias="a"):
    base = f"({alias}.status<>'DRAFT' OR {alias}.requester_user_id=:actor)"
    if not is_admin():
        base += (
            f" AND ({alias}.requester_user_id=:actor OR EXISTS "
            f"(SELECT 1 FROM approval_steps vs WHERE vs.approval_request_id={alias}.approval_request_id "
            "AND vs.approver_user_id=:actor))"
        )
    return base


def approval_row(conn, identifier, lock=False, check_scope=True):
    row = one(
        conn,
        "SELECT a.*,e.employee_name AS requester_name,d.department_name AS requester_department_name "
        f"{APPROVAL_JOINS} WHERE a.approval_request_id=:id AND e.company_id=:company"
        + (" FOR UPDATE" if lock else ""),
        {"id": identifier, "company": g.actor["company_id"]},
    )
    if not row:
        raise ApiError("APPROVAL_NOT_FOUND", 404)
    owner = row["requester_user_id"] == g.actor["user_id"]
    if check_scope:
        if row["status"] == "DRAFT" and not owner:
            raise ApiError("FORBIDDEN_SCOPE", 403)
        if (
            not is_admin()
            and not owner
            and not scalar(
                conn,
                "SELECT COUNT(*) FROM approval_steps WHERE approval_request_id=:id AND approver_user_id=:user",
                {"id": identifier, "user": g.actor["user_id"]},
            )
        ):
            raise ApiError("FORBIDDEN_SCOPE", 403)
    return row


def steps_for(conn, identifiers):
    groups = {identifier: [] for identifier in identifiers}
    if not groups:
        return groups
    params = {f"id_{index}": value for index, value in enumerate(groups)}
    placeholders = ",".join(f":{key}" for key in params)
    rows = all_rows(
        conn,
        "SELECT s.approval_request_id AS request_id,s.step_order,s.approver_user_id,e.employee_name AS approver_name,"
        "s.status,s.comments AS comment,s.decided_at AS processed_at,"
        "COALESCE(t.job_title_name,p.position_name) AS title "
        "FROM approval_steps s JOIN users u ON u.user_id=s.approver_user_id "
        "JOIN employees e ON e.employee_id=u.employee_id JOIN positions p ON p.position_id=e.position_id "
        f"LEFT JOIN job_titles t ON t.job_title_id=e.job_title_id WHERE s.approval_request_id IN ({placeholders}) "
        "ORDER BY s.approval_request_id,s.step_order",
        params,
    )
    for row in rows:
        groups[row.pop("request_id")].append(row)
    for steps in groups.values():
        for index, step in enumerate(steps):
            title = step.pop("title")
            step["label"] = "최종 승인" if index == len(steps) - 1 else f"{title} 결재"
    return groups


def approval_detail(conn, identifier):
    row = approval_row(conn, identifier)
    steps = steps_for(conn, [identifier])[identifier]
    allowed = []
    if row["status"] == "DRAFT" and row["requester_user_id"] == g.actor["user_id"]:
        allowed = ["SUBMIT"]
    elif row["status"] == "IN_PROGRESS" and any(
        step["status"] == "PENDING" and step["approver_user_id"] == g.actor["user_id"]
        for step in steps
    ):
        allowed = ["APPROVE", "REJECT"]
    return {
        "request_id": identifier,
        **{
            k: row[k]
            for k in ("request_type", "title", "content", "status", "requested_at", "completed_at")
        },
        "requester": {
            "user_id": row["requester_user_id"],
            "name": row["requester_name"],
            "department_name": row["requester_department_name"],
        },
        "steps": steps,
        "allowed_actions": allowed,
    }


def validate_approvers(conn, identifiers, submit):
    if not isinstance(identifiers, list) or len(identifiers) > 5 or (submit and not identifiers):
        raise ApiError("APPROVERS_INVALID")
    if any(type(value) is not int or value < 1 for value in identifiers):
        raise ApiError("APPROVERS_INVALID")
    if len(set(identifiers)) != len(identifiers) or g.actor["user_id"] in identifiers:
        raise ApiError("APPROVERS_INVALID")
    if identifiers:
        params = {f"id_{index}": value for index, value in enumerate(identifiers)}
        placeholders = ",".join(f":{key}" for key in params)
        eligible = scalar(
            conn,
            "SELECT COUNT(*) FROM users u JOIN employees e ON e.employee_id=u.employee_id "
            f"WHERE u.user_id IN ({placeholders}) AND e.company_id=:company AND u.status='ACTIVE' "
            "AND e.employment_status IN ('ACTIVE','ON_LEAVE') AND EXISTS "
            "(SELECT 1 FROM user_roles ur JOIN roles r ON r.role_id=ur.role_id "
            "WHERE ur.user_id=u.user_id AND r.is_active=1 AND r.role_code IN ('HR_ADMIN','EMPLOYEE'))",
            {**params, "company": g.actor["company_id"]},
        )
        if eligible != len(identifiers):
            raise ApiError("APPROVERS_INVALID")
