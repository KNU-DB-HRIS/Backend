"""HRIS NL2SQL 서비스 (FastAPI)

호출자는 Flask 하나뿐: POST /api/v1/ai/queries → 여기 POST /queries → SQL을 돌려주면 Flask가 검증·실행.
이 서비스는 DB에 접속하지 않는다(SQL 생성만). compose 내부망 + 127.0.0.1에만 노출.
"""
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import load_settings
from .llm import LLMError, make_client
from .service import generate

log = logging.getLogger("nl2sql")
DEFAULT_FUNCTIONS = ["ABS", "AVG", "CASE", "CAST", "CEIL", "COALESCE", "CONCAT", "COUNT", "CURRENT_DATE", "DATE", "DATEDIFF",
                     "DAY", "EXTRACT", "FLOOR", "IF", "LOWER", "MAX", "MIN", "MONTH", "NULLIF", "ROUND", "SUM",
                     "TIMESTAMPDIFF", "UPPER", "YEAR"]  # Flask가 functions를 안 보낼 때(구버전)만 사용


class QueryIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    question: str = Field(min_length=1, max_length=500)
    conversation_id: str | None = Field(default=None, max_length=200)
    schema_: dict[str, list[str]] = Field(alias="schema")
    functions: list[str] | None = None
    mode: Literal["simple", "enhanced"] | None = None  # 평가 하네스용. Flask는 안 보냄 → 기본 모드

    @field_validator("schema_")
    @classmethod
    def _schema_size(cls, v):
        if not v or len(v) > 20 or any(len(cols) > 80 for cols in v.values()):
            raise ValueError("schema must have 1-20 tables with up to 80 columns")
        return v


class QueryOut(BaseModel):
    status: Literal["SQL_READY", "NEEDS_CLARIFICATION", "OUT_OF_SCOPE", "GENERATION_FAILED"]
    sql: str | None
    answer: str | None
    mode: str
    model: str
    attempts: int
    precheck_errors: list[str]
    latency_ms: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    app.state.client = make_client(settings) if settings.configured else None
    if settings.fixture_file:
        log.warning("LLM_FIXTURE_FILE 사용 중: 실제 LLM이 아닌 고정 응답 (테스트 전용)")
    yield


app = FastAPI(title="HRIS NL2SQL", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health(request: Request):
    s = request.app.state.settings
    return {"status": "ok", "llm_configured": s.configured, "model": s.model_label, "default_mode": s.default_mode}


@app.post("/queries", response_model=QueryOut)
async def queries(body: QueryIn, request: Request):
    s, client = request.app.state.settings, request.app.state.client
    if client is None:
        raise HTTPException(503, "LLM_NOT_CONFIGURED")
    mode = body.mode or s.default_mode
    try:
        out = await generate(body.question.strip(), body.schema_, body.functions or DEFAULT_FUNCTIONS, mode, client, s)
    except LLMError as e:
        log.warning("llm error %s", e.code)
        raise HTTPException(e.status, e.code) from None
    log.info("query mode=%s status=%s attempts=%s %sms", mode, out["status"], out["attempts"], out["latency_ms"])
    return out
