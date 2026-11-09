from collections import Counter, defaultdict
from datetime import timedelta

from flask import g

from app.db import all_rows, one, scalar, today
from app.errors import ApiError
from app.modules.employees.services import employed, employment_rows

RESOURCES = {
    "departments": ("department", "DEPARTMENT", "department_code"),
    "positions": ("position", "POSITION", "position_level"),
    "job-titles": ("job_title", "JOB_TITLE", "job_title_code"),
    "jobs": ("job", "JOB", "job_code"),
}


def descendants(rows, root):
    children = defaultdict(list)
    for row in rows:
        children[row["parent_department_id"]].append(row["department_id"])
    result, pending = set(), [root]
    while pending:
        item = pending.pop()
        if item in result:
            continue
        result.add(item)
        pending.extend(children[item])
    return result


def department_totals(rows, counts):
    parents = {row["department_id"]: row["parent_department_id"] for row in rows}
    totals = {identifier: Counter() for identifier in parents}
    for identifier, values in counts.items():
        visited = set()
        while identifier in parents and identifier not in visited:
            totals[identifier].update(values)
            visited.add(identifier)
            identifier = parents[identifier]
    return totals


def organization_rows(conn, resource):
    stem, _, order = RESOURCES[resource]
    table = resource.replace("-", "_")
    fields = f"x.{stem}_id,x.{stem}_code,x.{stem}_name,x.description,x.is_active"
    join = ""
    if resource == "departments":
        fields += (
            ",x.parent_department_id,p.department_name AS parent_department_name,"
            "x.manager_employee_id,m.employee_name AS manager_name"
        )
        join = (
            " LEFT JOIN departments p ON p.department_id=x.parent_department_id "
            "LEFT JOIN employees m ON m.employee_id=x.manager_employee_id"
        )
    elif resource == "positions":
        fields += ",x.position_level AS level,x.min_tenure_months"
    elif resource == "jobs":
        fields += ",x.job_family,x.job_category"
    rows = all_rows(
        conn,
        f"SELECT {fields} FROM {table} x {join} "
        f"WHERE x.company_id=:company ORDER BY x.{order},x.{stem}_id",
        {"company": g.actor["company_id"]},
    )
    counts = {
        r["id"]: r["n"]
        for r in all_rows(
            conn,
            f"SELECT {stem}_id AS id,COUNT(*) AS n FROM employees WHERE company_id=:company "
            f"AND employment_status IN ('ACTIVE','ON_LEAVE') GROUP BY {stem}_id",
            {"company": g.actor["company_id"]},
        )
    }
    totals = (
        department_totals(rows, {key: {"headcount": value} for key, value in counts.items()})
        if resource == "departments"
        else None
    )
    for row in rows:
        identifier = row[f"{stem}_id"]
        row["is_active"] = bool(row["is_active"])
        row["headcount"] = counts.get(identifier, 0)
        if resource == "departments":
            row["direct_headcount"] = row["headcount"]
            row["headcount"] = totals[identifier]["headcount"]
    return rows


def get_resource(conn, resource, identifier, lock=False):
    stem, code, _ = RESOURCES[resource]
    row = one(
        conn,
        f"SELECT * FROM {resource.replace('-', '_')} WHERE {stem}_id=:id "
        "AND company_id=:company" + (" FOR UPDATE" if lock else ""),
        {"id": identifier, "company": g.actor["company_id"]},
    )
    if not row:
        raise ApiError(f"{code}_NOT_FOUND", 404)
    return row


def validate_reference(conn, table, key, value):
    if value is None:
        return
    if not scalar(
        conn,
        f"SELECT COUNT(*) FROM {table} WHERE {key}=:id AND company_id=:company AND is_active=1",
        {"id": value, "company": g.actor["company_id"]},
    ):
        raise ApiError("REFERENCE_INVALID")


def company_counts(conn):
    rows = employment_rows(conn)
    current = today()
    previous = current.replace(day=1) - timedelta(days=1)
    previous_start = previous.replace(day=1)
    present = [r for r in rows if r["employment_status"] in {"ACTIVE", "ON_LEAVE"}]
    total = len(present)
    active = sum(r["employment_status"] == "ACTIVE" for r in present)
    last_total = sum(employed(row, previous) for row in rows)
    hires = sum(current.replace(day=1) <= r["hire_date"] <= current for r in rows)
    last_hires = sum(previous_start <= r["hire_date"] <= previous for r in rows)
    return rows, {
        "total": total,
        "total_change_vs_last_month": total - last_total,
        "active": active,
        "active_rate": round(active / total, 4) if total else None,
        "on_leave": total - active,
        "on_leave_rate": round((total - active) / total, 4) if total else None,
        "new_hires_this_month": hires,
        "new_hires_change_vs_last_month": hires - last_hires,
    }
