from importlib import import_module

from flask import Flask, g, request

from app.config import load_config
from app.db import JSONProvider, init_db
from app.errors import register_errors


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(load_config())
    app.json = JSONProvider(app)
    init_db(app)
    register_errors(app)

    from app.cli import register_commands
    from app.health import bp as health_bp

    app.register_blueprint(health_bp)
    for module in (
        "auth", "dashboard", "employees", "payroll", "organization",
        "evaluations", "approvals", "documents", "search", "ai",
    ):
        app.register_blueprint(
            import_module(f"app.modules.{module}.routes").bp, url_prefix="/api/v1"
        )
    register_commands(app)

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        origin = request.headers.get("Origin")
        if origin in app.config["CORS_ORIGINS"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
            response.vary.add("Origin")
        session_cookie = getattr(g, "session_cookie", None)
        if session_cookie:
            response.set_cookie(
                app.config["SESSION_COOKIE_NAME"], session_cookie,
                max_age=app.config["SESSION_IDLE_SECONDS"], httponly=True,
                secure=app.config["SESSION_COOKIE_SECURE"], samesite="Lax", path="/api/v1",
            )
        return response

    return app
