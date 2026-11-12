"""질문 → SQL 생성 (사전 점검에 걸리면 1회 수리). Flask가 20초에 끊으니 전체 예산 안에서만 재시도"""
import time

from .llm import LLMError
from .prompts import build_messages, repair_message
from .sqlcheck import UnparseableOutput, clean_sql, parse_output, precheck

# Flask routes.py는 status == NEEDS_CLARIFICATION 과 sql 유무만 본다. 나머지 필드는 평가·로그용
STATUS_MAP = {"OK": "SQL_READY", "NEEDS_CLARIFICATION": "NEEDS_CLARIFICATION", "OUT_OF_SCOPE": "OUT_OF_SCOPE"}


async def generate(question: str, schema: dict, functions: list[str], mode: str, client, settings) -> dict:
    t0 = time.monotonic()
    left = lambda: settings.deadline - (time.monotonic() - t0)  # noqa: E731
    messages = build_messages(mode, question, schema, functions)
    attempts, problems, parsed = 0, [], None
    while True:
        attempts += 1
        raw = await client.complete(messages, timeout=max(1.0, min(settings.llm_timeout, left())))
        try:
            parsed = parse_output(raw)
            problems = []
            if parsed["status"] == "OK":
                parsed["sql"] = clean_sql(parsed["sql"])
                problems = precheck(parsed["sql"], schema, functions)
        except UnparseableOutput:
            parsed, problems = None, ["출력이 JSON 형식이 아님"]
        if not problems or attempts > settings.max_repairs or left() < 3:
            break
        messages = messages + [{"role": "assistant", "content": raw}, repair_message(problems)]
    out = {"mode": mode, "model": getattr(client, "model", "-"), "attempts": attempts,
           "precheck_errors": problems, "latency_ms": int((time.monotonic() - t0) * 1000)}
    if parsed is None:
        return {**out, "status": "GENERATION_FAILED", "sql": None, "answer": "질문을 SQL로 바꾸지 못했습니다. 다르게 물어봐 주세요."}
    # 사전 점검에 끝까지 걸려도 SQL은 그대로 넘김 → Flask 검증기가 최종 판정(SQL_REJECTED)
    return {**out, "status": STATUS_MAP[parsed["status"]], "sql": parsed["sql"], "answer": parsed["answer"]}


__all__ = ["generate", "LLMError"]
