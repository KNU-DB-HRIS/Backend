import io
import re
import secrets
from collections import Counter, defaultdict
from xml.etree import ElementTree

from defusedxml.ElementTree import fromstring
from flask import Blueprint, current_app, g, request, send_file
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError

from app.db import audit, insert, lock_company, one, scalar, today, transaction, update
from app.errors import ApiError
from app.modules.organization.services import (
    RESOURCES,
    company_counts,
    department_totals,
    descendants,
    get_resource,
    organization_rows,
    validate_reference,
)
from app.security import require_auth
from app.validation import (
    body,
    date_field,
    email,
    int_field,
    page_result,
    pagination,
    query_bool,
    query_choice,
    query_int,
    query_text,
    text_field,
)

bp = Blueprint("organization", __name__)

COMPANY_FIELDS = {
    "name": text_field(100),
    "name_en": text_field(100, True),
    "business_number": text_field(20),
    "ceo_name": text_field(50, True),
    "founded_date": date_field(True),
    "address": text_field(200, True),
    "phone": text_field(20, True),
    "email": lambda v, k: email(v, k, True),
    "homepage": text_field(200, True),
    "industry": text_field(50, True),
    "logo_url": text_field(500, True),
}
COMPANY_SELECT = (
    "company_id,company_name AS name,name_en,business_number,ceo_name,founded_date,"
    "address,phone,email,homepage,industry,logo_url"
)


@bp.get("/company")
@require_auth(admin=True)
def company():
    with transaction() as conn:
        return one(
            conn,
            f"SELECT {COMPANY_SELECT} FROM companies WHERE company_id=:id",
            {"id": g.actor["company_id"]},
        )


@bp.patch("/company")
@require_auth(admin=True)
def edit_company():
    data = body(COMPANY_FIELDS)
    if "business_number" in data and not re.fullmatch(
        r"\d{3}-\d{2}-\d{5}", data["business_number"]
    ):
        raise ApiError("VALIDATION_ERROR", details={"field": "business_number"})
    if data.get("homepage") and not data["homepage"].startswith(("http://", "https://")):
        raise ApiError("VALIDATION_ERROR", details={"field": "homepage"})
    with transaction() as conn:
        lock_company(conn, g.actor["company_id"])
        if data.get("logo_url"):
            prefix = "/api/v1/company/logos/"
            logo = data["logo_url"]
            if not logo.startswith(prefix) or not scalar(
                conn,
                "SELECT COUNT(*) FROM uploaded_logos WHERE logo_id=:id AND company_id=:company",
                {"id": logo[len(prefix) :], "company": g.actor["company_id"]},
            ):
                raise ApiError("VALIDATION_ERROR", details={"field": "logo_url"})
        if "name" in data:
            data["company_name"] = data.pop("name")
        try:
            update(conn, "companies", "company_id", g.actor["company_id"], data)
        except IntegrityError:
            raise ApiError("BUSINESS_NUMBER_DUPLICATE", 409) from None
        audit(conn, "COMPANY_UPDATED", "company", g.actor["company_id"])
        return one(
            conn,
            f"SELECT {COMPANY_SELECT} FROM companies WHERE company_id=:id",
            {"id": g.actor["company_id"]},
        )


def resource_fields(resource):
    stem, _, _ = RESOURCES[resource]
    limits = {
        "department": (20, 200),
        "position": (20, 50),
        "job_title": (50, 200),
        "job": (100, 500),
    }
    name_limit, description_limit = limits[stem]
    fields = {
        f"{stem}_name": text_field(name_limit),
        f"{stem}_code": text_field(20),
        "description": text_field(description_limit, True),
    }
    required = [f"{stem}_name", f"{stem}_code"]
    if resource == "departments":
        fields.update(
            parent_department_id=int_field(nullable=True),
            manager_employee_id=int_field(nullable=True),
        )
    if resource == "positions":
        fields.update(level=int_field(), min_tenure_months=int_field(0, nullable=True))
        required.append("level")
    if resource == "jobs":
        fields.update(job_family=text_field(20), job_category=text_field(30))
        required.extend(("job_family", "job_category"))
    return fields, required


def validate_resource(conn, resource, data, identifier=None, current=None):
    if resource == "departments":
        if data.get("parent_department_id") is not None:
            if identifier and data["parent_department_id"] in descendants(
                organization_rows(conn, resource), identifier
            ):
                raise ApiError("PARENT_CYCLE")
            validate_reference(conn, "departments", "department_id", data["parent_department_id"])
        if data.get("manager_employee_id") is not None:
            if not scalar(
                conn,
                "SELECT COUNT(*) FROM employees WHERE employee_id=:id "
                "AND company_id=:company AND employment_status='ACTIVE'",
                {"id": data["manager_employee_id"], "company": g.actor["company_id"]},
            ):
                raise ApiError("MANAGER_NOT_ELIGIBLE")
    if resource == "positions" and "level" in data:
        if current is None or current["is_active"]:
            if scalar(
                conn,
                "SELECT COUNT(*) FROM positions WHERE company_id=:company "
                "AND is_active=1 AND position_level=:level AND position_id<>:id",
                {"company": g.actor["company_id"], "level": data["level"], "id": identifier or 0},
            ):
                raise ApiError("POSITION_LEVEL_DUPLICATE", 409)
        data["position_level"] = data.pop("level")


def register_resource(resource):
    stem, code, _ = RESOURCES[resource]
    table = resource.replace("-", "_")

    @require_auth(admin=True)
    def listing():
        q, active_only = query_text(), query_bool("active_only")
        with transaction() as conn:
            rows = organization_rows(conn, resource)
        rows = [
            r
            for r in rows
            if (not active_only or r["is_active"])
            and (
                not q
                or q.casefold() in r[f"{stem}_name"].casefold()
                or q.casefold() in r[f"{stem}_code"].casefold()
            )
        ]
        return {"items": rows, "total": len(rows)}

    @require_auth(admin=True)
    def detail(identifier):
        with transaction() as conn:
            get_resource(conn, resource, identifier)
            return next(
                r for r in organization_rows(conn, resource) if r[f"{stem}_id"] == identifier
            )

    @require_auth(admin=True)
    def save(identifier=None):
        fields, required = resource_fields(resource)
        readonly = ("headcount", "direct_headcount", "parent_department_name", "manager_name")
        data = body(fields, required if identifier is None else (), readonly=readonly)
        with transaction() as conn:
            lock_company(conn, g.actor["company_id"])
            current = get_resource(conn, resource, identifier, True) if identifier else None
            validate_resource(conn, resource, data, identifier, current)
            try:
                if identifier:
                    update(conn, table, f"{stem}_id", identifier, data)
                else:
                    identifier = insert(conn, table, {**data, "company_id": g.actor["company_id"]})
            except IntegrityError:
                raise ApiError(f"{code}_CODE_DUPLICATE", 409) from None
            audit(
                conn,
                "ORGANIZATION_UPDATED" if current else "ORGANIZATION_CREATED",
                table,
                identifier,
            )
            result = next(
                r for r in organization_rows(conn, resource) if r[f"{stem}_id"] == identifier
            )
        return result, 200 if current else 201

    @require_auth(admin=True)
    def deactivate(identifier):
        with transaction() as conn:
            lock_company(conn, g.actor["company_id"])
            current = get_resource(conn, resource, identifier, True)
            if not current["is_active"]:
                raise ApiError("ALREADY_INACTIVE", 409)
            if scalar(
                conn,
                f"SELECT COUNT(*) FROM employees WHERE {stem}_id=:id "
                "AND employment_status IN ('ACTIVE','ON_LEAVE')",
                {"id": identifier},
            ):
                raise ApiError(f"{code}_IN_USE", 409)
            if resource == "departments" and scalar(
                conn,
                "SELECT COUNT(*) FROM departments WHERE parent_department_id=:id AND is_active=1",
                {"id": identifier},
            ):
                raise ApiError("DEPARTMENT_HAS_CHILDREN", 409)
            update(conn, table, f"{stem}_id", identifier, {"is_active": False})
            audit(conn, "ORGANIZATION_DEACTIVATED", table, identifier)
        return "", 204

    bp.add_url_rule(f"/{resource}", f"{stem}_list", listing, methods=["GET"])
    bp.add_url_rule(f"/{resource}/<int:identifier>", f"{stem}_detail", detail, methods=["GET"])
    bp.add_url_rule(f"/{resource}", f"{stem}_create", save, methods=["POST"])
    bp.add_url_rule(f"/{resource}/<int:identifier>", f"{stem}_update", save, methods=["PATCH"])
    bp.add_url_rule(
        f"/{resource}/<int:identifier>", f"{stem}_delete", deactivate, methods=["DELETE"]
    )


for resource_name in RESOURCES:
    register_resource(resource_name)


@bp.get("/organization/headcounts")
@require_auth(admin=True)
def headcounts():
    page, size = pagination()
    q = query_text()
    status = query_choice("employment_status", ("ACTIVE", "ON_LEAVE"))
    division = query_int("division_id")
    with transaction() as conn:
        departments = organization_rows(conn, "departments")
        if division and not any(
            department["department_id"] == division and department["is_active"]
            for department in departments
        ):
            raise ApiError("VALIDATION_ERROR", details={"field": "division_id"})
        employees, summary = company_counts(conn)
    permitted = descendants(departments, division) if division else None
    day = today()
    counts = defaultdict(Counter)
    for employee in employees:
        if employee["employment_status"] in {"ACTIVE", "ON_LEAVE"}:
            counts[employee["department_id"]].update(
                total=1,
                active=int(employee["employment_status"] == "ACTIVE"),
                new_hires=int(day.replace(day=1) <= employee["hire_date"] <= day),
            )
    totals = department_totals(departments, counts)
    result = []
    for department in departments:
        if not department["is_active"] or (
            permitted is not None and department["department_id"] not in permitted
        ):
            continue
        if q and not any(
            q.casefold() in (department.get(k) or "").casefold()
            for k in ("department_name", "manager_name")
        ):
            continue
        count = totals[department["department_id"]]
        total, active = count["total"], count["active"]
        leave = total - active
        if status and not (active if status == "ACTIVE" else leave):
            continue
        result.append(
            {
                "department_id": department["department_id"],
                "department_name": department["department_name"],
                "manager_name": department["manager_name"],
                "total": total,
                "active": active,
                "on_leave": leave,
                "active_rate": round(active / total, 4) if total else None,
                "new_hires": count["new_hires"],
            }
        )
    return {"summary": summary, **page_result(result, page, size)}


@bp.post("/company/logo")
@require_auth(admin=True)
def upload_logo():
    upload = request.files.get("file")
    if upload is None:
        raise ApiError("VALIDATION_ERROR", details={"field": "file"})
    data = upload.stream.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise ApiError("FILE_TOO_LARGE", 413)
    if upload.mimetype == "image/svg+xml":
        try:
            root = fromstring(data)
            allowed = {
                "svg",
                "g",
                "path",
                "circle",
                "rect",
                "ellipse",
                "line",
                "polyline",
                "polygon",
                "defs",
                "clipPath",
                "linearGradient",
                "radialGradient",
                "stop",
                "text",
                "tspan",
                "title",
                "desc",
            }
            for node in root.iter():
                if node.tag.split("}")[-1] not in allowed:
                    raise ValueError()
                for key, value in node.attrib.items():
                    if key.split("}")[-1].lower().startswith("on") or key.split("}")[-1] in {
                        "href",
                        "style",
                    }:
                        raise ValueError()
                    if "url(" in value.lower() and not re.fullmatch(
                        r"url\(#[A-Za-z0-9_-]+\)", value
                    ):
                        raise ValueError()
            if root.tag.split("}")[-1] != "svg":
                raise ValueError()
            data = ElementTree.tostring(root, encoding="utf-8")
            extension, media = "svg", "image/svg+xml"
        except Exception:
            raise ApiError("UNSUPPORTED_MEDIA_TYPE", 415) from None
    else:
        try:
            with Image.open(io.BytesIO(data)) as img:
                if img.format not in {"JPEG", "PNG"} or img.width * img.height > 16000000:
                    raise ValueError()
                extension, media = (
                    ("jpg", "image/jpeg") if img.format == "JPEG" else ("png", "image/png")
                )
                img.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise ApiError("UNSUPPORTED_MEDIA_TYPE", 415) from None
    identifier = secrets.token_hex(16)
    directory = current_app.config["STORAGE_DIR"] / "logos"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{identifier}.{extension}"
    path.write_bytes(data)
    try:
        with transaction() as conn:
            insert(
                conn,
                "uploaded_logos",
                {
                    "logo_id": identifier,
                    "company_id": g.actor["company_id"],
                    "file_name": path.name,
                    "media_type": media,
                },
            )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"logo_url": f"/api/v1/company/logos/{identifier}"}, 201


@bp.get("/company/logos/<identifier>")
@require_auth(admin=True)
def logo_file(identifier):
    with transaction() as conn:
        logo = one(
            conn,
            "SELECT file_name,media_type FROM uploaded_logos WHERE logo_id=:id AND company_id=:company",
            {"id": identifier, "company": g.actor["company_id"]},
        )
    if not logo:
        raise ApiError("NOT_FOUND", 404)
    path = current_app.config["STORAGE_DIR"] / "logos" / logo["file_name"]
    if not path.is_file():
        raise ApiError("NOT_FOUND", 404)
    response = send_file(path, mimetype=logo["media_type"])
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
