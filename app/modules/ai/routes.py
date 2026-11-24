import secrets

import requests
import sqlglot
from flask import Blueprint, current_app, g
from sqlalchemy.exc import SQLAlchemyError

from app.errors import ApiError
from app.modules.ai.executor import ExecutorConfigError, run_readonly
from app.modules.ai.sql_policy import SAFE_FUNCTIONS, SAFE_TABLES, display_sql, validate_sql
from app.security import require_auth
from app.validation import body, text_field

bp = Blueprint("ai", __name__)


def result(
    status="FAILED", error=None, answer=None, sql=None, columns=None, rows=None, truncated=False, shown_sql=None
):
    """sql: 실제 실행한 SQL(회사 범위 하위 질의 포함, 한 줄). display_sql: 화면용(절마다 줄바꿈, 회사 범위는 scope_company_id로 안내)"""
    return {
        "query_id": "q_" + secrets.token_hex(8),
        "status": status,
        "error_code": error,
        "answer": answer,
        "sql": sql,
        "display_sql": shown_sql,
        "scope_company_id": g.actor["company_id"] if sql else None,
        "columns": columns or [],
        "rows": rows or [],
        "row_count": len(rows or []),
        "truncated": truncated,
    }


@bp.post("/ai/queries")
@require_auth(permission="AI_QUERY")
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
            # functions: FastAPI가 프롬프트·사전 점검에 같은 허용 목록을 쓰도록 함께 보냄(목록이 두 군데로 갈라지지 않게)
            json={**data, "schema": SAFE_TABLES, "functions": sorted(SAFE_FUNCTIONS)},
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
        # 범위 밖(급여·연락처 등)이라 SQL을 안 만든 경우, 그 이유를 사용자에게 그대로 보여줌
        return result(error="SQL_GENERATION_FAILED", answer=answer)
    try:
        sql = validate_sql(generated["sql"], g.actor["company_id"])
    except (ValueError, sqlglot.errors.SqlglotError):
        return result(error="SQL_REJECTED")
    try:
        columns, rows, truncated = run_readonly(
            sql,
            current_app.config["AI_DATABASE_URL"],
            {current_app.extensions["db"].url.username},
        )
    except (ExecutorConfigError, SQLAlchemyError):
        return result(error="SQL_EXECUTION_FAILED")
    try:
        shown = display_sql(generated["sql"])
    except (ValueError, sqlglot.errors.SqlglotError):
        shown = None
    return result(
        "ANSWERED" if rows else "NO_RESULT",
        answer=answer,
        sql=sql,
        shown_sql=shown,
        columns=columns,
        rows=rows,
        truncated=truncated,
    )
