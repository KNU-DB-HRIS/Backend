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


def load_actor(conn, user_id):
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
    roles = all_rows(
        conn,
        "SELECT r.role_code,r.role_name FROM roles r JOIN user_roles ur "
        "ON ur.role_id=r.role_id WHERE ur.user_id=:id AND r.is_active=1",
        {"id": user_id},
    )
    actor["roles"] = [r["role_code"] for r in roles]
    if not set(actor["roles"]) & {"HR_ADMIN", "EMPLOYEE"}:
        raise ApiError("FORBIDDEN", 403)
    actor["role_label"] = next(
        (r["role_name"] for r in roles if r["role_code"] == "HR_ADMIN"), roles[0]["role_name"]
    )
    granted = all_rows(
        conn,
        "SELECT DISTINCT p.permission_code FROM permissions p "
        "JOIN role_permissions rp ON rp.permission_id=p.permission_id "
        "JOIN user_roles ur ON ur.role_id=rp.role_id "
        "JOIN roles r ON r.role_id=ur.role_id "
        "WHERE ur.user_id=:id AND p.is_active=1 AND r.is_active=1 "
        "AND p.permission_code LIKE 'MENU_%'",
        {"id": user_id},
    )
    order = ("DASHBOARD", "EMPLOYEES", "PAYROLL", "ORGANIZATION", "EVALUATION", "DOCUMENTS", "AI")
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
                g.actor = load_actor(conn, session["user_id"])
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
