import secrets

import requests
import sqlglot
from flask import Blueprint, current_app, g
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.errors import ApiError
from app.modules.ai.sql_policy import SAFE_TABLES, validate_sql
from app.security import require_auth
from app.validation import body, text_field

bp = Blueprint("ai", __name__)


def result(
    status="FAILED", error=None, answer=None, sql=None, columns=None, rows=None, truncated=False
):
    return {
        "query_id": "q_" + secrets.token_hex(8),
        "status": status,
        "error_code": error,
        "answer": answer,
        "sql": sql,
        "columns": columns or [],
        "rows": rows or [],
        "row_count": len(rows or []),
        "truncated": truncated,
    }


@bp.post("/ai/queries")
@require_auth(admin=True, error_code="AI_ADMIN_ONLY")
def query():
    data = body(
        {"question": text_field(500), "conversation_id": text_field(200, True)}, ("question",)
    )
    upstream = current_app.config["AI_BASE_URL"]
    if not upstream:
        raise ApiError("AI_UPSTREAM_ERROR", 502)
    try:
        response = requests.post(
            upstream.rstrip("/") + "/queries",
            json={**data, "schema": SAFE_TABLES},
            timeout=(3, current_app.config["AI_TIMEOUT_SECONDS"]),
            allow_redirects=False,
        )
        if response.status_code != 200 or len(response.content) > 512000:
            raise ApiError("AI_UPSTREAM_ERROR", 502)
        generated = response.json()
        if not isinstance(generated, dict):
            raise ValueError()
    except requests.Timeout:
        raise ApiError("AI_TIMEOUT", 504) from None
    except (requests.RequestException, ValueError):
        raise ApiError("AI_UPSTREAM_ERROR", 502) from None
    answer = generated.get("answer")
    if answer is not None and not isinstance(answer, str):
        raise ApiError("AI_UPSTREAM_ERROR", 502)
    if generated.get("status") == "NEEDS_CLARIFICATION":
        return result("NEEDS_CLARIFICATION", answer=answer)
    if not generated.get("sql"):
        return result(error="SQL_GENERATION_FAILED")
    try:
        sql = validate_sql(generated["sql"], g.actor["company_id"])
    except (ValueError, sqlglot.errors.SqlglotError):
        return result(error="SQL_REJECTED")
    database_url = current_app.config["AI_DATABASE_URL"]
    if not database_url:
        return result(error="SQL_EXECUTION_FAILED")
    engine = None
    try:
        url = make_url(database_url)
        if url.drivername != "mysql+pymysql" or url.username in {
            None,
            "root",
            current_app.extensions["db"].url.username,
        }:
            return result(error="SQL_EXECUTION_FAILED")
        engine = create_engine(
            url,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"connect_timeout": 3, "read_timeout": 7},
        )
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.exec_driver_sql("SET SESSION MAX_EXECUTION_TIME=5000")
            conn.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
            query_tree = sqlglot.parse_one(sql, read="mysql").limit(201)
            queried = conn.exec_driver_sql(query_tree.sql(dialect="mysql"))
            columns = list(queried.keys())
            rows = [list(row) for row in queried.fetchmany(201)]
        return result(
            "ANSWERED" if rows else "NO_RESULT",
            answer=answer,
            sql=sql,
            columns=columns,
            rows=rows[:200],
            truncated=len(rows) > 200,
        )
    except SQLAlchemyError:
        return result(error="SQL_EXECUTION_FAILED")
    finally:
        if engine is not None:
            engine.dispose()
