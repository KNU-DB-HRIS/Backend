"""일정 표시 대상 계산 (조회 시점): 대상 부서 목록, 표시 라벨, 대상 인원, 사원별 표시 여부"""
from collections import defaultdict

from flask import g

from app.db import all_rows, scalar
from app.modules.organization.services import descendants

EMPLOYED = "('ACTIVE','ON_LEAVE')"


def company_departments(conn, company_id=None):
    return all_rows(
        conn,
        "SELECT department_id,parent_department_id,department_name,is_active FROM departments WHERE company_id=:c",
        {"c": company_id or g.actor["company_id"]},
    )


def target_rows(conn, event_ids):
    if not event_ids:
        return {}
    ids = ",".join(str(int(i)) for i in event_ids)
    rows = all_rows(
        conn,
        "SELECT t.event_id,t.department_id,t.include_children,d.department_name,d.is_active "
        "FROM hr_event_departments t JOIN departments d ON d.department_id=t.department_id "
        f"WHERE t.event_id IN ({ids}) ORDER BY d.department_name,t.department_id",
    )
    result = defaultdict(list)
    for r in rows:
        result[r["event_id"]].append({
            "department_id": r["department_id"], "department_name": r["department_name"],
            "include_children": bool(r["include_children"]), "is_active": bool(r["is_active"]),
        })
    return result


def target_label(scope, targets):
    if scope == "COMPANY":
        return "전사"
    if not targets:
        return "대상 없음"
    first = targets[0]["department_name"]
    text = first if len(targets) == 1 else f"{first} 외 {len(targets) - 1}개 조직"
    if any(t["include_children"] for t in targets):
        text += ", 하위 포함"
    return text[:100]


def attach_targets(conn, rows):
    targets = target_rows(conn, [r["event_id"] for r in rows])
    for r in rows:
        r["all_day"] = bool(r.get("all_day"))
        r["targets"] = targets.get(r["event_id"], [])
        r["target_label"] = target_label(r.get("scope") or "COMPANY", r["targets"])
    return rows


def audience_departments(conn, targets):
    rows = company_departments(conn)
    ids = set()
    for t in targets:
        ids |= descendants(rows, t["department_id"]) if t["include_children"] else {t["department_id"]}
    return ids


def audience_count(conn, scope, targets):
    """표시 대상 재직자(휴직 포함) 수, 현재 회사 기준"""
    if scope == "COMPANY":
        return scalar(
            conn,
            f"SELECT COUNT(*) FROM employees WHERE company_id=:c AND employment_status IN {EMPLOYED}",
            {"c": g.actor["company_id"]},
        )
    ids = audience_departments(conn, targets)
    if not ids:
        return 0
    return scalar(
        conn,
        f"SELECT COUNT(*) FROM employees WHERE company_id=:c AND employment_status IN {EMPLOYED} "
        f"AND department_id IN ({','.join(str(int(i)) for i in ids)})",
        {"c": g.actor["company_id"]},
    )


def department_chain(conn, company_id, department_id):
    """내 부서와 모든 상위 부서 (사원에게 보일 일정 판정용)"""
    parents = {r["department_id"]: r["parent_department_id"] for r in company_departments(conn, company_id)}
    chain, current = [], department_id
    while current is not None and current not in chain:
        chain.append(current)
        current = parents.get(current)
    return chain
