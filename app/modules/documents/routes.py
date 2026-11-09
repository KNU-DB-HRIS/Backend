import re
import secrets

from flask import Blueprint, current_app, g, send_file

from app.db import all_rows, audit, insert, now, one, today, transaction
from app.errors import ApiError
from app.modules.documents.pdf import render_pdf
from app.modules.employees.services import assignments, employee_profile, employee_row
from app.security import require_auth, scope_employee
from app.validation import body, choice_field, int_field, text_field

bp = Blueprint("documents", __name__)

MONEY_FIELDS = (
    "base_salary",
    "position_allowance",
    "meal_allowance",
    "other_allowance",
    "gross_pay",
    "national_pension",
    "health_insurance",
    "long_term_care",
    "employment_insurance",
    "income_tax",
    "local_income_tax",
    "total_deduction",
    "net_pay",
)


def issue(employee_id, kind, build_payload, key):
    scope_employee(employee_id)
    path = None
    try:
        with transaction() as conn:
            employee = employee_row(conn, employee_id)
            payload = build_payload(conn, employee)
            company = one(
                conn,
                "SELECT company_name FROM companies WHERE company_id=:id",
                {"id": g.actor["company_id"]},
            )
            issued_at = now()
            relative = f"documents/{secrets.token_hex(16)}.pdf"
            path = current_app.config["STORAGE_DIR"] / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            render_pdf(path, kind, company, employee, payload, issued_at)
            name = f"{kind.lower()}_{employee['employee_no']}_{issued_at:%Y%m%d}.pdf"
            document_id = insert(
                conn,
                "documents",
                {
                    "employee_id": employee_id,
                    "document_type": kind,
                    "file_name": name,
                    "file_path": relative,
                    "issued_by_user_id": g.actor["user_id"],
                    "issued_at": issued_at,
                },
            )
            action = {"PAYSLIP": "PAYSLIP_ISSUED", "WITHHOLDING": "WITHHOLDING_ISSUED"}.get(
                kind, "CERTIFICATE_ISSUED"
            )
            audit(
                conn,
                action,
                "payroll_statement" if kind in {"PAYSLIP", "WITHHOLDING"} else "document",
                document_id,
            )
        return {
            "document_id": document_id,
            "document_type": kind,
            "issued_at": issued_at,
            "file_url": f"/api/v1/documents/{document_id}/file",
            key: payload,
        }, 201
    except Exception:
        if path:
            path.unlink(missing_ok=True)
        raise


@bp.post("/certificates")
@require_auth()
def certificate():
    data = body(
        {"certificate_type": choice_field("EMPLOYMENT", "CAREER"), "employee_id": int_field()},
        ("certificate_type", "employee_id"),
    )

    def payload(conn, employee):
        if data["certificate_type"] == "EMPLOYMENT" and employee["employment_status"] not in {
            "ACTIVE",
            "ON_LEAVE",
        }:
            raise ApiError("NOT_EMPLOYED", 409)
        detail = employee_profile(conn, employee["employee_id"])
        keys = (
            "employee_no",
            "name",
            "birth_date",
            "department_name",
            "position_name",
            "job_name",
            "hire_date",
            "termination_date",
        )
        result = {key: detail[key] for key in keys}
        result.update(as_of=today(), career=[])
        if data["certificate_type"] == "CAREER":
            result["career"] = [
                {
                    "effective_date": row["effective_date"],
                    "action_type": row["action_type"],
                    "department_name": row["to_department_name"],
                    "position_name": row["to_position_name"],
                }
                for row in reversed(assignments(conn, employee["employee_id"]))
            ]
        return result

    return issue(data["employee_id"], data["certificate_type"], payload, "certificate")


@bp.post("/certificates/payslip")
@require_auth()
def payslip():
    data = body(
        {"employee_id": int_field(), "pay_month": text_field(7)}, ("employee_id", "pay_month")
    )
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", data["pay_month"]):
        raise ApiError("VALIDATION_ERROR", details={"field": "pay_month"})

    def payload(conn, employee):
        row = one(
            conn,
            "SELECT pay_month,status,paid_at,"
            + ",".join(MONEY_FIELDS)
            + " FROM payroll_statements WHERE employee_id=:id AND pay_month=:month AND status IN ('CONFIRMED','PAID')",
            {"id": employee["employee_id"], "month": data["pay_month"]},
        )
        if not row:
            raise ApiError("PAYSLIP_NOT_FOUND", 404)
        return row

    return issue(data["employee_id"], "PAYSLIP", payload, "statement")


@bp.post("/certificates/withholding")
@require_auth()
def withholding():
    data = body(
        {"employee_id": int_field(), "year": int_field(1900, 9999)}, ("employee_id", "year")
    )

    def payload(conn, employee):
        rows = all_rows(
            conn,
            "SELECT * FROM payroll_statements WHERE employee_id=:id AND status='PAID' "
            "AND pay_month BETWEEN :start AND :end ORDER BY pay_month",
            {
                "id": employee["employee_id"],
                "start": f"{data['year']}-01",
                "end": f"{data['year']}-12",
            },
        )
        if not rows:
            raise ApiError("NO_PAID_STATEMENTS", 404)
        return {
            "year": data["year"],
            "months": len(rows),
            "first_month": rows[0]["pay_month"],
            "last_month": rows[-1]["pay_month"],
            **{
                key: sum(row[key] for row in rows)
                for key in ("gross_pay", "income_tax", "local_income_tax", "net_pay")
            },
            "social_insurance": sum(
                sum(
                    row[k]
                    for k in (
                        "national_pension",
                        "health_insurance",
                        "long_term_care",
                        "employment_insurance",
                    )
                )
                for row in rows
            ),
        }

    return issue(data["employee_id"], "WITHHOLDING", payload, "summary")


@bp.get("/documents/<int:document_id>/file")
@require_auth()
def document_file(document_id):
    with transaction() as conn:
        row = one(
            conn,
            "SELECT d.* FROM documents d JOIN employees e ON e.employee_id=d.employee_id "
            "WHERE d.document_id=:id AND e.company_id=:company",
            {"id": document_id, "company": g.actor["company_id"]},
        )
    if not row:
        raise ApiError("DOCUMENT_NOT_FOUND", 404)
    scope_employee(row["employee_id"])
    root = current_app.config["STORAGE_DIR"].resolve()
    path = (root / row["file_path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ApiError("DOCUMENT_NOT_FOUND", 404)
    return send_file(
        path, mimetype="application/pdf", as_attachment=True, download_name=row["file_name"]
    )
