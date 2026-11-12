"""환경 변수 설정 (LLM 키는 이 컨테이너에만 들어오고 Flask에는 안 감)"""
import json
import os
from dataclasses import dataclass, field

MODES = ("simple", "enhanced")
_RESERVED = {"model", "messages", "temperature", "response_format", "stream"}


def _extra_body(raw: str) -> dict:
    """LLM_EXTRA_BODY: 제공자 전용 옵션(JSON). 예) DeepSeek 생각 모드 끄기 {"thinking":{"type":"disabled"}}"""
    if not raw.strip():
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict) or _RESERVED & set(value):
        raise ValueError(f"LLM_EXTRA_BODY must be a JSON object without {sorted(_RESERVED)}")
    return value


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout: float
    llm_json_mode: bool
    default_mode: str
    fixture_file: str
    max_repairs: int
    deadline: float
    llm_extra_body: dict = field(default_factory=dict)

    @property
    def configured(self) -> bool:
        # 로컬 Ollama 같은 경우 키가 없어도 됨 → 주소·모델만 필수
        return bool(self.fixture_file or (self.llm_base_url and self.llm_model))

    @property
    def model_label(self) -> str:
        return "fixture" if self.fixture_file else (self.llm_model or "-")


def load_settings() -> Settings:
    mode = os.getenv("NL2SQL_PROMPT_MODE", "enhanced").strip() or "enhanced"
    if mode not in MODES:
        raise ValueError(f"NL2SQL_PROMPT_MODE must be one of {MODES}")
    return Settings(
        llm_base_url=os.getenv("LLM_BASE_URL", "").strip().rstrip("/"),
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_model=os.getenv("LLM_MODEL", "").strip(),
        llm_timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "12")),
        llm_json_mode=os.getenv("LLM_JSON_MODE", "0").strip() in {"1", "true", "yes"},
        default_mode=mode,
        fixture_file=os.getenv("LLM_FIXTURE_FILE", "").strip(),
        max_repairs=int(os.getenv("NL2SQL_MAX_REPAIRS", "1")),
        # Flask는 20초 뒤 끊음(AI_TIMEOUT_SECONDS) → 그 전에 답하도록 전체 예산
        deadline=float(os.getenv("NL2SQL_DEADLINE_SECONDS", "17")),
        llm_extra_body=_extra_body(os.getenv("LLM_EXTRA_BODY", "")),
    )
