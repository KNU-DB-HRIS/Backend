from flask import Blueprint

from app.db import scalar, transaction
from app.errors import ApiError

bp = Blueprint("health", __name__)


@bp.get("/health/live")
def live():
    return {"status": "ok"}, 200


@bp.get("/health/ready")
def ready():
    with transaction() as conn:
        count = scalar(
            conn, "SELECT COUNT(*) FROM schema_migrations WHERE name='018_company_scoped_evaluations.sql'"
        )
    if count != 1:
        raise ApiError("SCHEMA_NOT_READY", 503)
    return {"status": "ok"}
