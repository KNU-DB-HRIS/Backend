from flask import Blueprint, g, request

from app.db import (
    all_rows,
    audit,
    execute,
    insert,
    lock_company,
    now,
    one,
    page_query,
    scalar,
    transaction,
    update,
)
from app.errors import ApiError
from app.modules.approvals.services import (
    APPROVAL_JOINS,
    approval_detail,
    approval_row,
    steps_for,
    validate_approvers,
    visible_condition,
)
from app.security import require_auth
from app.validation import (
    body,
    boolean,
    choice_field,
    pagination,
    query_choice,
    text_field,
)

bp = Blueprint("approvals", __name__)


@bp.get("/approvals/summary")
@require_auth()
def summary():
    with transaction() as conn:
        counts = {
            row["status"]: row["n"]
            for row in all_rows(
                conn,
                "SELECT status,COUNT(*) AS n FROM approval_requests WHERE requester_user_id=:id GROUP BY status",
                {"id": g.actor["user_id"]},
            )
        }
        pending = scalar(
            conn,
            "SELECT COUNT(*) FROM approval_requests a WHERE a.status='IN_PROGRESS' AND EXISTS "
            "(SELECT 1 FROM approval_steps s WHERE s.approval_request_id=a.approval_request_id "
            "AND s.status='PENDING' AND s.approver_user_id=:id)",
            {"id": g.actor["user_id"]},
        )
    return {
        "my_pending": pending,
        "approved": counts.get("APPROVED", 0),
        "rejected": counts.get("REJECTED", 0),
        "drafts": counts.get("DRAFT", 0),
    }


@bp.get("/approvals")
@require_auth()
def listing():
    page, size = pagination(10)
    tab = query_choice("tab", ("to_approve", "in_progress", "archive"), "to_approve")
    status = query_choice("status", ("DRAFT", "IN_PROGRESS", "APPROVED", "REJECTED"))
    conditions = ["e.company_id=:company", visible_condition()]
    if tab == "to_approve":
        conditions.append(
            "a.status='IN_PROGRESS' AND EXISTS (SELECT 1 FROM approval_steps x "
            "WHERE x.approval_request_id=a.approval_request_id AND x.approver_user_id=:actor AND x.status='PENDING')"
        )
    elif tab == "in_progress":
        conditions.append("a.status='IN_PROGRESS'")
    else:
        conditions.append("a.status IN ('DRAFT','APPROVED','REJECTED')")
    if status:
        conditions.append("a.status=:status")
    params = {
        "company": g.actor["company_id"],
        "actor": g.actor["user_id"],
        "status": status,
    }
    clause = APPROVAL_JOINS + " WHERE " + " AND ".join(conditions)
    with transaction() as conn:
        result = page_query(
            conn,
            "a.approval_request_id AS request_id,a.title,a.request_type,a.status,"
            "DATE(a.requested_at) AS requested_at,e.employee_name AS requester_name,"
            "d.department_name AS requester_department_name",
            clause,
            params,
            "a.requested_at DESC,a.approval_request_id DESC",
            page,
            size,
        )
        grouped_steps = steps_for(conn, [row["request_id"] for row in result["items"]])
        for row in result["items"]:
            steps = grouped_steps[row["request_id"]]
            row["current_step_label"] = next(
                (s["label"] for s in steps if s["status"] == "PENDING"), None
            )
            row["steps"] = [{k: s[k] for k in ("step_order", "label", "status")} for s in steps]
    return result


@bp.get("/approvals/<int:request_id>")
@require_auth()
def detail(request_id):
    with transaction() as conn:
        return approval_detail(conn, request_id)


@bp.post("/approvals")
@require_auth()
def create_approval():
    data = body(
        {
            "request_type": choice_field(
                "LEAVE", "EXPENSE", "COOPERATION", "BUSINESS_TRIP", "GENERAL"
            ),
            "title": text_field(100),
            "content": text_field(500, True),
            "submit": boolean,
            "approver_user_ids": lambda value, field: value,
        },
        ("request_type", "title"),
    )
    submit = data.pop("submit", False)
    identifiers = data.pop("approver_user_ids", [])
    with transaction() as conn:
        lock_company(conn, g.actor["company_id"])
        validate_approvers(conn, identifiers, submit)
        identifier = insert(
            conn,
            "approval_requests",
            {
                **data,
                "requester_user_id": g.actor["user_id"],
                "status": "IN_PROGRESS" if submit else "DRAFT",
            },
        )
        for index, approver in enumerate(identifiers, 1):
            insert(
                conn,
                "approval_steps",
                {
                    "approval_request_id": identifier,
                    "step_order": index,
                    "approver_user_id": approver,
                    "status": "PENDING" if submit and index == 1 else "WAITING",
                },
            )
        audit(conn, "APPROVAL_SUBMITTED" if submit else "APPROVAL_DRAFTED", "approval", identifier)
        return approval_detail(conn, identifier), 201


@bp.post("/approvals/<int:request_id>/submit")
@require_auth()
def submit_approval(request_id):
    with transaction() as conn:
        lock_company(conn, g.actor["company_id"])
        row = approval_row(conn, request_id, True, False)
        if row["requester_user_id"] != g.actor["user_id"]:
            raise ApiError("NOT_REQUESTER", 403)
        if row["status"] != "DRAFT":
            raise ApiError("INVALID_STATE", 409)
        steps = steps_for(conn, [request_id])[request_id]
        validate_approvers(conn, [s["approver_user_id"] for s in steps], True)
        update(
            conn,
            "approval_requests",
            "approval_request_id",
            request_id,
            {"status": "IN_PROGRESS", "requested_at": now()},
        )
        execute(
            conn,
            "UPDATE approval_steps SET status='PENDING' WHERE approval_request_id=:id AND step_order=1",
            {"id": request_id},
        )
        audit(conn, "APPROVAL_SUBMITTED", "approval", request_id)
        return approval_detail(conn, request_id)


def process(request_id, reject=False):
    if request.content_length:
        data = body({"comment": text_field(500, not reject)}, ("comment",) if reject else ())
    elif reject:
        raise ApiError("VALIDATION_ERROR", details={"field": "comment"})
    else:
        data = {}
    with transaction() as conn:
        row = approval_row(conn, request_id, True, False)
        if row["status"] != "IN_PROGRESS":
            raise ApiError("INVALID_STATE", 409)
        step = one(
            conn,
            "SELECT * FROM approval_steps WHERE approval_request_id=:id AND status='PENDING' "
            "ORDER BY step_order LIMIT 1 FOR UPDATE",
            {"id": request_id},
        )
        if not step or step["approver_user_id"] != g.actor["user_id"]:
            raise ApiError("NOT_CURRENT_APPROVER", 403)
        status = "REJECTED" if reject else "APPROVED"
        changed = execute(
            conn,
            "UPDATE approval_steps SET status=:status,comments=:comment,decided_at=:at "
            "WHERE approval_step_id=:id AND status='PENDING'",
            {
                "status": status,
                "comment": data.get("comment"),
                "at": now(),
                "id": step["approval_step_id"],
            },
        )
        if changed.rowcount != 1:
            raise ApiError("ALREADY_PROCESSED", 409)
        if reject:
            execute(
                conn,
                "UPDATE approval_steps SET status='SKIPPED' WHERE approval_request_id=:id "
                "AND status IN ('WAITING','PENDING')",
                {"id": request_id},
            )
        else:
            following = one(
                conn,
                "SELECT approval_step_id FROM approval_steps WHERE approval_request_id=:id "
                "AND status='WAITING' ORDER BY step_order LIMIT 1 FOR UPDATE",
                {"id": request_id},
            )
            if following:
                update(
                    conn,
                    "approval_steps",
                    "approval_step_id",
                    following["approval_step_id"],
                    {"status": "PENDING"},
                )
                status = "IN_PROGRESS"
        update(
            conn,
            "approval_requests",
            "approval_request_id",
            request_id,
            {"status": status, "completed_at": None if status == "IN_PROGRESS" else now()},
        )
        audit(conn, "APPROVAL_REJECTED" if reject else "APPROVAL_APPROVED", "approval", request_id)
    return {"request_id": request_id, "status": status}


@bp.post("/approvals/<int:request_id>/approve")
@require_auth()
def approve(request_id):
    return process(request_id)


@bp.post("/approvals/<int:request_id>/reject")
@require_auth()
def reject(request_id):
    return process(request_id, True)
