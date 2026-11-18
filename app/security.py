import hashlib
import hmac
import secrets
from datetime import timedelta
from functools import wraps

from flask import current_app, g, request
from werkzeug.security import generate_password_hash

from app.db import all_rows, insert, now, one, transaction, update
from app.errors import ApiError


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_account(conn, employee_id, username, password, role_id):
    user_id = insert(
        conn,
        "users",
        {
            "employee_id": employee_id,
            "username": username,
            "password_hash": generate_password_hash(password),
            "status": "ACTIVE",
        },
    )
    insert(conn, "user_roles", {"user_id": user_id, "role_id": role_id})
    return user_id


def company_role_rows(conn, user_id, company_id):
    """소속 회사 밖의 회사에서 이 사용자가 가진 역할 (user_company_roles, 활성 회사만)"""
    return all_rows(
        conn,
        "SELECT r.role_id,r.role_code,r.role_name FROM user_company_roles ucr "
        "JOIN roles r ON r.role_id=ucr.role_id AND r.is_active=1 "
        "JOIN companies c ON c.company_id=ucr.company_id AND c.is_active=1 "
        "WHERE ucr.user_id=:user AND ucr.company_id=:company",
        {"user": user_id, "company": company_id},
    )


def accessible_companies(conn, user_id, home_company_id):
    """회사 전환 메뉴에 보일 회사: 소속 회사 + user_company_roles로 역할이 있는 활성 회사"""
    return all_rows(
        conn,
        "SELECT c.company_id,c.company_name AS name,g.group_name,"
        "(c.company_id=:home) AS is_home,"
        "(SELECT COUNT(*) FROM employees e WHERE e.company_id=c.company_id "
        "AND e.employment_status IN ('ACTIVE','ON_LEAVE')) AS headcount "
        "FROM companies c LEFT JOIN company_groups g ON g.group_id=c.group_id "
        "WHERE c.is_active=1 AND (c.company_id=:home OR EXISTS (SELECT 1 FROM user_company_roles ucr "
        "JOIN roles r ON r.role_id=ucr.role_id AND r.is_active=1 "
        "WHERE ucr.user_id=:user AND ucr.company_id=c.company_id)) "
        "ORDER BY (c.company_id=:home) DESC, c.company_name",
        {"user": user_id, "home": home_company_id},
    )


def load_actor(conn, user_id, active_company_id=None):
    actor = one(
        conn,
        "SELECT u.user_id,u.username,u.status,e.employee_id,e.employee_name,"
        "e.employee_no,e.company_id,e.employment_status,d.department_name,p.position_name "
        "FROM users u JOIN employees e ON e.employee_id=u.employee_id "
        "JOIN companies c ON c.company_id=e.company_id AND c.is_active=1 "
        "JOIN departments d ON d.department_id=e.department_id "
        "JOIN positions p ON p.position_id=e.position_id WHERE u.user_id=:id",
        {"id": user_id},
    )
    if not actor or actor["status"] != "ACTIVE" or actor["employment_status"] == "TERMINATED":
        raise ApiError("UNAUTHENTICATED", 401)
    actor["home_company_id"] = actor["company_id"]
    roles = all_rows(
        conn,
        "SELECT r.role_id,r.role_code,r.role_name FROM roles r JOIN user_roles ur "
        "ON ur.role_id=r.role_id WHERE ur.user_id=:id AND r.is_active=1",
        {"id": user_id},
    )
    if active_company_id and int(active_company_id) != actor["company_id"]:
        # 계열사 전환: 그 회사에 부여된 역할이 있을 때만. 없으면(권한 회수 등) 소속 회사로 되돌아감
        company_roles = company_role_rows(conn, user_id, active_company_id)
        if company_roles:
            actor["company_id"], roles = int(active_company_id), company_roles
    actor["roles"] = [r["role_code"] for r in roles]
    if not set(actor["roles"]) & {"HR_ADMIN", "EMPLOYEE"}:
        raise ApiError("FORBIDDEN", 403)
    actor["role_label"] = next(
        (r["role_name"] for r in roles if r["role_code"] == "HR_ADMIN"), roles[0]["role_name"]
    )
    role_params = {f"r{i}": r["role_id"] for i, r in enumerate(roles)}
    granted = all_rows(
        conn,
        "SELECT DISTINCT p.permission_code FROM permissions p "
        "JOIN role_permissions rp ON rp.permission_id=p.permission_id "
        f"WHERE rp.role_id IN ({','.join(':' + k for k in role_params)}) AND p.is_active=1 "
        "AND p.permission_code LIKE 'MENU_%'",
        role_params,
    )
    order = ("DASHBOARD", "EMPLOYEES", "PAYROLL", "ORGANIZATION", "EVALUATION", "DOCUMENTS", "SCHEDULE", "AI")
    allowed = {p["permission_code"].removeprefix("MENU_") for p in granted}
    actor["menus"] = [menu for menu in order if menu in allowed]
    actor["ip"] = request.remote_addr
    return actor


def is_admin():
    return "HR_ADMIN" in g.actor["roles"]


def csrf_check(session):
    value = request.headers.get("X-CSRF-Token", "")
    if not value or not hmac.compare_digest(digest(value), session["csrf_hash"]):
        raise ApiError("CSRF_INVALID", 403)


def require_auth(admin=False, error_code="FORBIDDEN"):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            cookie = request.cookies.get(current_app.config["SESSION_COOKIE_NAME"], "")
            if not cookie or len(cookie) > 256:
                raise ApiError("UNAUTHENTICATED", 401)
            with transaction() as conn:
                session = one(
                    conn,
                    "SELECT * FROM auth_sessions WHERE session_id=:sid",
                    {"sid": digest(cookie)},
                )
                if not session or session["revoked_at"] or session["expires_at"] <= now():
                    raise ApiError("UNAUTHENTICATED", 401)
                g.actor = load_actor(conn, session["user_id"], session.get("active_company_id"))
                g.auth_session = session
                if admin and not is_admin():
                    raise ApiError(error_code, 403)
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    csrf_check(session)
                update(
                    conn,
                    "auth_sessions",
                    "session_id",
                    session["session_id"],
                    {"expires_at": now() + timedelta(seconds=current_app.config["SESSION_IDLE_SECONDS"])},
                )
            g.session_cookie = cookie
            return function(*args, **kwargs)

        return wrapped

    return decorate


def scope_employee(employee_id):
    if not is_admin() and g.actor["employee_id"] != employee_id:
        raise ApiError("FORBIDDEN_SCOPE", 403)


def new_csrf(conn, session_id):
    value = secrets.token_urlsafe(32)
    update(conn, "auth_sessions", "session_id", session_id, {"csrf_hash": digest(value)})
    return value
