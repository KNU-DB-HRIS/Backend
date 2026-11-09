import secrets
from datetime import timedelta

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import audit, execute, insert, now, one, transaction, update
from app.errors import ApiError
from app.security import digest, load_actor, new_csrf, require_auth
from app.validation import body, string, text_field

bp = Blueprint("auth", __name__)
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(32))


def password_field(value, field):
    string(value, field, 128)
    return value


@bp.post("/auth/login")
def login():
    data = body(
        {"username": text_field(50), "password": password_field},
        required=("username", "password"),
    )
    attempt_key = digest(f"{request.remote_addr}:{data['username'].casefold()}")
    failure = None
    with transaction() as conn:
        execute(
            conn,
            "INSERT IGNORE INTO auth_login_attempts VALUES(:key,0,:at)",
            {"key": attempt_key, "at": now()},
        )
        attempts = one(
            conn,
            "SELECT * FROM auth_login_attempts WHERE attempt_key=:key FOR UPDATE",
            {"key": attempt_key},
        )
        if attempts["window_started_at"] < now() - timedelta(minutes=15):
            update(conn, "auth_login_attempts", "attempt_key", attempt_key,
                   {"failures": 0, "window_started_at": now()})
            attempts["failures"] = 0
        if attempts["failures"] >= 10:
            raise ApiError("RATE_LIMITED", 429)
        user = one(
            conn,
            "SELECT user_id,password_hash,status FROM users WHERE username=:username",
            {"username": data["username"]},
        )
        valid = check_password_hash(user["password_hash"] if user else DUMMY_HASH, data["password"])
        if not user or not valid:
            update(conn, "auth_login_attempts", "attempt_key", attempt_key,
                   {"failures": attempts["failures"] + 1})
            failure = ApiError("INVALID_CREDENTIALS", 401)
        elif user["status"] != "ACTIVE":
            failure = ApiError("ACCOUNT_DISABLED", 403)
        else:
            try:
                g.actor = load_actor(conn, user["user_id"])
            except ApiError as exc:
                if exc.code == "UNAUTHENTICATED":
                    raise ApiError("ACCOUNT_DISABLED", 403) from None
                raise
            execute(
                conn,
                "SET @hris_actor_user_id=:id, @hris_actor_ip_address=:ip",
                {"id": user["user_id"], "ip": request.remote_addr},
            )
            opaque_cookie = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(32)
            insert(
                conn,
                "auth_sessions",
                {
                    "session_id": digest(opaque_cookie),
                    "user_id": user["user_id"],
                    "csrf_hash": digest(csrf),
                    "expires_at": now() + timedelta(seconds=current_app.config["SESSION_IDLE_SECONDS"]),
                },
            )
            update(conn, "users", "user_id", user["user_id"], {"last_login_at": now()})
            update(conn, "auth_login_attempts", "attempt_key", attempt_key, {"failures": 0})
            audit(conn, "LOGIN", "user", user["user_id"])
    if failure:
        raise failure
    response = jsonify(
        user_id=g.actor["user_id"],
        employee_id=g.actor["employee_id"],
        employee_name=g.actor["employee_name"],
        roles=g.actor["roles"],
        csrf_token=csrf,
    )
    response.set_cookie(
        current_app.config["SESSION_COOKIE_NAME"], opaque_cookie,
        max_age=current_app.config["SESSION_IDLE_SECONDS"], httponly=True,
        secure=current_app.config["SESSION_COOKIE_SECURE"], samesite="Lax", path="/api/v1",
    )
    return response


@bp.post("/auth/logout")
@require_auth()
def logout():
    with transaction() as conn:
        update(conn, "auth_sessions", "session_id", g.auth_session["session_id"],
               {"revoked_at": now()})
        audit(conn, "LOGOUT", "user", g.actor["user_id"])
    g.session_cookie = None
    response = current_app.response_class(status=204)
    response.delete_cookie(
        current_app.config["SESSION_COOKIE_NAME"], path="/api/v1",
        secure=current_app.config["SESSION_COOKIE_SECURE"], httponly=True, samesite="Lax",
    )
    return response


@bp.get("/auth/me")
@require_auth()
def me():
    with transaction() as conn:
        csrf = new_csrf(conn, g.auth_session["session_id"])
    return {
        "user_id": g.actor["user_id"],
        "username": g.actor["username"],
        "employee_id": g.actor["employee_id"],
        "employee_name": g.actor["employee_name"],
        "employee_no": g.actor["employee_no"],
        "department_name": g.actor["department_name"],
        "position_name": g.actor["position_name"],
        "roles": g.actor["roles"],
        "role_label": g.actor["role_label"],
        "menus": g.actor["menus"],
        "csrf_token": csrf,
    }
