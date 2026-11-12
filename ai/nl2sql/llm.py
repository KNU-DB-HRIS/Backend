"""LLM 호출: OpenAI 호환 /chat/completions 하나로 OpenAI·Gemini·OpenRouter·Ollama를 모두 지원

fixture 모드는 키 없이 배선(Flask↔FastAPI↔DB)을 시험하기 위한 것. 응답의 model이 "fixture"로 표시된다.
"""
import json
from pathlib import Path

import httpx


class LLMError(Exception):
    def __init__(self, code: str, status: int = 502):
        super().__init__(code)
        self.code, self.status = code, status


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str, json_mode: bool = False, extra_body: dict | None = None):
        self.base_url, self.api_key, self.model, self.json_mode = base_url, api_key, model, json_mode
        self.extra_body = extra_body or {}

    def request_body(self, messages: list[dict]) -> dict:
        body = {**self.extra_body, "model": self.model, "messages": messages, "temperature": 0}
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    async def complete(self, messages: list[dict], timeout: float) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = self.request_body(messages)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                r = await client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
        except httpx.TimeoutException:
            raise LLMError("LLM_TIMEOUT", 504) from None
        except httpx.HTTPError:
            raise LLMError("LLM_UNREACHABLE", 502) from None
        if r.status_code == 429:
            raise LLMError("LLM_RATE_LIMITED", 503)
        if r.status_code in (401, 403):
            raise LLMError("LLM_AUTH_FAILED", 502)
        if r.status_code != 200:
            raise LLMError(f"LLM_HTTP_{r.status_code}", 502)
        try:
            content = r.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError("LLM_BAD_RESPONSE", 502) from None
        # JSON 모드에서 JSON이 못 되면 빈 문자열이 올 수 있음(DeepSeek 문서) → 오류 대신 빈 답으로 넘겨 수리 1회
        return content if isinstance(content, str) else ""


class FixtureClient:
    """질문 → 미리 적은 응답. 키 '모드:질문'이 먼저, 없으면 '질문'"""

    model = "fixture"

    def __init__(self, path: str):
        self.table = json.loads(Path(path).read_text(encoding="utf-8"))

    async def complete(self, messages: list[dict], timeout: float) -> str:
        question = messages[-1]["content"] if messages[-1]["role"] == "user" else ""
        mode = "enhanced" if "[업무 용어" in messages[0]["content"] else "simple"
        hit = self.table.get(f"{mode}:{question}") or self.table.get(question)
        if hit is None:
            hit = {"status": "NEEDS_CLARIFICATION", "sql": None, "answer": "(fixture) 등록되지 않은 질문입니다."}
        return json.dumps(hit, ensure_ascii=False)


def make_client(settings):
    if settings.fixture_file:
        return FixtureClient(settings.fixture_file)
    return OpenAICompatibleClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model, settings.llm_json_mode,
                                  settings.llm_extra_body)
