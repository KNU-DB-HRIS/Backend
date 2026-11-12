#!/usr/bin/env python3
"""NL2SQL 평가 하네스 — Simple vs 보강(enhanced) 프롬프트를 L1~L3 질문으로 비교

실행(백엔드 컨테이너 안, 실서비스와 같은 검증기·읽기 전용 실행부 사용):
    bash ./setup/ai-eval.sh                 # 두 방식 1회씩
    bash ./setup/ai-eval.sh --repeat 3      # 반복해서 흔들림 확인
결과: ai/eval/out/report.md (발표·보고서용 표), ai/eval/out/results.json (생성 SQL 전부)

판정 경로: 질문 → FastAPI(/queries, mode 지정) → sql_policy.validate_sql(회사 범위 주입) → executor.run_readonly
          정답 SQL도 같은 경로로 실행해 결과 집합을 비교 (scoring.py)
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = ["/app", str(HERE)]

import requests  # noqa: E402
import sqlglot  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from app.config import load_config  # noqa: E402
from app.modules.ai.executor import ExecutorConfigError, run_readonly  # noqa: E402
from app.modules.ai.sql_policy import SAFE_FUNCTIONS, SAFE_TABLES, validate_sql  # noqa: E402
from scoring import VERDICTS, verdict  # noqa: E402

LEVELS = ("L1", "L2", "L3")


def company_and_app_user():
    url = load_config()["DATABASE_URL"]
    engine = create_engine(url)
    try:
        with engine.connect() as c:
            cid = c.execute(text("SELECT company_id FROM companies ORDER BY company_id LIMIT 1")).scalar()
    finally:
        engine.dispose()
    if cid is None:
        sys.exit("회사 데이터가 없음 → bash ./setup/database-data.sh 먼저")
    return cid, engine.url.username


def execute(sql, cid, ai_db, forbidden):
    """(rejected_reason, exec_error, rows)"""
    try:
        safe = validate_sql(sql, cid)
    except (ValueError, sqlglot.errors.SqlglotError) as e:
        return str(e) or "rejected", None, None
    try:
        _, rows, _ = run_readonly(safe, ai_db, forbidden)
        return None, None, rows
    except (ExecutorConfigError, SQLAlchemyError) as e:
        return None, type(e).__name__ + ": " + str(e).splitlines()[0][:200], None


def ask(ai_url, question, mode):
    body = {"question": question, "schema": SAFE_TABLES, "functions": sorted(SAFE_FUNCTIONS), "mode": mode}
    try:
        r = requests.post(ai_url.rstrip("/") + "/queries", json=body, timeout=60)
    except requests.RequestException as e:
        return {"status": "AI_ERROR", "error": type(e).__name__}
    if r.status_code != 200:
        try:
            detail = r.json().get("detail")
        except ValueError:
            detail = r.text[:200]
        return {"status": "AI_ERROR", "error": f"HTTP {r.status_code} {detail}"}
    return r.json()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ai-url", default=os.getenv("AI_BASE_URL") or "http://ai:8000")
    p.add_argument("--modes", default="simple,enhanced")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--only", default="", help="질문 ID 접두어 (예: L3)")
    p.add_argument("--out", default=str(HERE / "out"))
    p.add_argument("--sleep", type=float, default=0.0, help="호출 사이 대기(무료 티어 분당 한도 대비)")
    a = p.parse_args()
    modes = [m.strip() for m in a.modes.split(",") if m.strip()]
    qs = [q for q in json.loads((HERE / "questions.json").read_text(encoding="utf-8"))["questions"] if q["id"].startswith(a.only)]
    ai_db = os.getenv("AI_DATABASE_URL", "")
    cid, app_user = company_and_app_user()
    forbidden = {app_user}
    health = requests.get(a.ai_url.rstrip("/") + "/health", timeout=10).json()
    if not health.get("llm_configured"):
        sys.exit("AI 서비스에 LLM이 설정되지 않음 (.env의 LLM_BASE_URL·LLM_MODEL·LLM_API_KEY)")

    gold = {}
    for q in qs:  # 정답 SQL부터 같은 경로로 실행 — 하나라도 실패하면 평가 중단(데이터·정책 불일치)
        if "gold_sql" in q:
            rej, err, rows = execute(q["gold_sql"], cid, ai_db, forbidden)
            if rej or err:
                sys.exit(f"정답 SQL 실패 {q['id']}: {rej or err}")
            gold[q["id"]] = rows

    results, started = [], dt.datetime.now().astimezone()
    for rep in range(1, a.repeat + 1):
        for q in qs:
            for mode in modes:
                res = ask(a.ai_url, q["question"], mode)
                sql = res.get("sql")
                rej = err = rows = None
                if sql and res.get("status") == "SQL_READY":
                    rej, err, rows = execute(sql, cid, ai_db, forbidden)
                v = verdict(q, res.get("status"), sql, rej, err, gold.get(q["id"]), rows)
                results.append({"run": rep, "id": q["id"], "level": q["level"], "mode": mode, "question": q["question"],
                                "verdict": v, "ai_status": res.get("status"), "sql": sql, "answer": res.get("answer"),
                                "rejected": rej, "exec_error": err, "precheck_errors": res.get("precheck_errors"),
                                "attempts": res.get("attempts"), "latency_ms": res.get("latency_ms"), "ai_error": res.get("error"),
                                "gold_sql": q.get("gold_sql"), "rule": q.get("rule")})
                print(f"[{rep}] {q['id']} {mode:8} {v}", flush=True)
                time.sleep(a.sleep)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = {"started": started.isoformat(timespec="seconds"), "model": health.get("model"), "modes": modes, "repeat": a.repeat,
            "questions": len(qs), "company_id": cid}
    (out / "results.json").write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=1, default=str),
                                      encoding="utf-8")
    (out / "report.md").write_text(report(meta, qs, results, modes), encoding="utf-8")
    print(f"\n→ {out / 'report.md'}")


def report(meta, qs, results, modes):
    by = defaultdict(list)
    for r in results:
        by[(r["level"], r["mode"])].append(r["verdict"] == "CORRECT")
    pct = lambda xs: f"{sum(xs)}/{len(xs)} ({100 * sum(xs) / len(xs):.0f}%)" if xs else "-"  # noqa: E731
    L = [f"# NL2SQL 평가 결과 ({meta['started'][:16].replace('T', ' ')})", "",
         f"- 모델 `{meta['model']}` · 질문 {meta['questions']}개 × 방식 {len(modes)} × 반복 {meta['repeat']}",
         "- 판정: 생성 SQL과 정답 SQL을 같은 서버 검증기·읽기 전용 계정으로 실행해 결과 집합 비교",
         "- simple = 테이블·열 이름만 / enhanced = + PK·FK·관계·열 의미·코드값·업무 용어·집계 기준·예시", "",
         "## 수준별 정답률", "", "| 수준 | " + " | ".join(modes) + " |", "|---|" + "---|" * len(modes)]
    for lv in LEVELS:
        L.append(f"| {lv} | " + " | ".join(pct(by[(lv, m)]) for m in modes) + " |")
    L.append("| 전체 | " + " | ".join(pct([x for lv in LEVELS for x in by[(lv, m)]]) for m in modes) + " |")
    L += ["", "## 오류 유형", "", "| 판정 | " + " | ".join(modes) + " |", "|---|" + "---|" * len(modes)]
    cnt = {m: Counter(r["verdict"] for r in results if r["mode"] == m) for m in modes}
    for v in VERDICTS:
        if any(cnt[m][v] for m in modes):
            L.append(f"| {v} | " + " | ".join(str(cnt[m][v]) for m in modes) + " |")
    L += ["", "## 질문별", "", "| ID | 질문 | " + " | ".join(modes) + " |", "|---|---|" + "---|" * len(modes)]
    for q in qs:
        cells = []
        for m in modes:
            vs = [r["verdict"] for r in results if r["id"] == q["id"] and r["mode"] == m]
            cells.append(" / ".join("✅" if v == "CORRECT" else v for v in vs))
        L.append(f"| {q['id']} | {q['question']} | " + " | ".join(cells) + " |")
    wrong = [r for r in results if r["verdict"] != "CORRECT"]
    if wrong:
        L += ["", "## 오답 분석용 상세", ""]
        for r in wrong:
            L += [f"### {r['id']} · {r['mode']} · {r['verdict']}" + (f" (반복 {r['run']})" if meta["repeat"] > 1 else ""),
                  f"- 질문: {r['question']}" + (f" · 규칙: {r['rule']}" if r.get("rule") else ""),
                  f"- AI 상태: {r['ai_status']}" + (f" · 답변: {r['answer']}" if r.get("answer") else "")]
            for k, label in (("rejected", "서버 거부"), ("exec_error", "실행 오류"), ("ai_error", "AI 오류")):
                if r.get(k):
                    L.append(f"- {label}: {r[k]}")
            if r.get("precheck_errors"):
                L.append(f"- 사전 점검(수리 후에도): {'; '.join(r['precheck_errors'])}")
            if r.get("sql"):
                L += ["- 생성 SQL", "```sql", r["sql"], "```"]
            if r.get("gold_sql"):
                L += ["- 정답 SQL", "```sql", r["gold_sql"], "```"]
            L.append("")
    L += ["", "## 한계", "",
          "- 샘플 데이터(직원 10명)가 작아 틀린 SQL이 우연히 같은 결과를 낼 수 있음",
          "- L3 정답은 prompts.py GLOSSARY의 업무 규칙(팀 합의 전 제안값) 기준. 규칙이 바뀌면 정답 SQL도 같이 수정",
          "- temperature 0이어도 모델 응답은 바뀔 수 있음 → --repeat로 흔들림 확인"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
