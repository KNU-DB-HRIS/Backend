"""NL2SQL 서비스 단위 테스트 (LLM은 가짜). 실행: cd ai && python -m pytest -q
Flask 쪽 계약 테스트는 백엔드 패키지가 설치된 환경에서만 돈다(importorskip).
"""
import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nl2sql.config import Settings
from nl2sql.llm import LLMError
from nl2sql.main import DEFAULT_FUNCTIONS, app
from nl2sql.prompts import build_messages
from nl2sql.service import generate
from nl2sql.sqlcheck import UnparseableOutput, clean_sql, parse_output, precheck

BACKEND = Path(__file__).resolve().parents[2]
SCHEMA = {  # Flask SAFE_TABLES와 같은 모양(JSON으로 오면 list)
    "employees": ["employee_id", "company_id", "employee_no", "employee_name", "hire_date", "termination_date", "employment_type",
                  "employment_status", "department_id", "position_id", "job_id", "job_title_id"],
    "departments": ["department_id", "company_id", "parent_department_id", "department_code", "department_name", "is_active"],
    "positions": ["position_id", "company_id", "position_code", "position_name", "position_level", "is_active"],
    "job_titles": ["job_title_id", "company_id", "job_title_code", "job_title_name", "is_active"],
}
S = Settings("http://llm", "", "fake-model", 5, False, "enhanced", "", 1, 17)


class Fake:
    model = "fake-model"

    def __init__(self, *outputs):
        self.outputs, self.calls = list(outputs), []

    async def complete(self, messages, timeout):
        self.calls.append(messages)
        o = self.outputs.pop(0)
        if isinstance(o, Exception):
            raise o
        return o if isinstance(o, str) else json.dumps(o, ensure_ascii=False)


run = lambda coro: asyncio.run(coro)  # noqa: E731
OK_SQL = "SELECT COUNT(*) AS `재직 인원` FROM employees WHERE employment_status = 'ACTIVE'"


# ---------- 사전 점검 ----------
@pytest.mark.parametrize("sql", [
    OK_SQL,
    "SELECT d.department_name AS `부서`, COUNT(*) AS n FROM employees e JOIN departments d ON d.department_id = e.department_id GROUP BY d.department_name HAVING COUNT(*) >= 3",
    "SELECT employee_name FROM employees WHERE YEAR(hire_date) = YEAR(CURRENT_DATE)",
    "SELECT employee_name FROM employees WHERE hire_date = (SELECT MAX(hire_date) FROM employees)",
])
def test_precheck_accepts(sql):
    assert precheck(sql, SCHEMA, DEFAULT_FUNCTIONS) == []


@pytest.mark.parametrize("sql,needle", [
    ("SELECT employee_name FROM employees UNION SELECT department_name FROM departments", "SELECT 한 문장"),
    ("WITH x AS (SELECT employee_id FROM employees) SELECT employee_id FROM x", "WITH"),
    ("SELECT employee_name FROM employees -- hi", "주석"),
    ("SELECT current_salary FROM employees", "쓸 수 없는 열: current_salary"),
    ("SELECT score FROM employee_evaluations", "없는 테이블: employee_evaluations"),
    ("SELECT NOW() AS n FROM employees", "허용되지 않은 함수"),
    ("SELECT employee_name FROM employees WHERE hire_date >= DATE_SUB(CURRENT_DATE, INTERVAL 1 DAY)", "DATE_SUB"),
    ("SELECT * FROM employees", "SELECT *"),
    ("SELECT employee_name FROM employees LIMIT 5 OFFSET 5", "OFFSET"),
    ("SELEC employee_name FROM", "문법 오류"),
])
def test_precheck_rejects(sql, needle):
    assert any(needle in p for p in precheck(sql, SCHEMA, DEFAULT_FUNCTIONS)), precheck(sql, SCHEMA, DEFAULT_FUNCTIONS)


def test_clean_sql_strips_semicolon_and_comments():
    assert clean_sql(OK_SQL + ";") == OK_SQL
    cleaned = clean_sql("SELECT employee_name FROM employees -- 재직자\n WHERE employment_status = 'ACTIVE';")
    assert "--" not in cleaned and precheck(cleaned, SCHEMA, DEFAULT_FUNCTIONS) == []


# ---------- 출력 파싱 ----------
def test_parse_json_in_fence():
    raw = '설명\n```json\n{"status":"OK","sql":"SELECT 1 AS a FROM employees","answer":"x"}\n```'
    assert parse_output(raw) == {"status": "OK", "sql": "SELECT 1 AS a FROM employees", "answer": "x"}


def test_parse_sql_only_fence():
    assert parse_output("```sql\nSELECT employee_name FROM employees\n```")["sql"] == "SELECT employee_name FROM employees"


def test_parse_clarification_drops_sql():
    p = parse_output('{"status":"NEEDS_CLARIFICATION","sql":"SELECT 1","answer":"누구요?"}')
    assert p == {"status": "NEEDS_CLARIFICATION", "sql": None, "answer": "누구요?"}


@pytest.mark.parametrize("raw", ["모르겠어요", '{"status":"OK","sql":null}'])
def test_parse_garbage(raw):
    with pytest.raises(UnparseableOutput):
        parse_output(raw)


# ---------- 생성 루프 ----------
def test_generate_ok():
    out = run(generate("재직 인원", SCHEMA, DEFAULT_FUNCTIONS, "enhanced", Fake({"status": "OK", "sql": OK_SQL, "answer": "a"}), S))
    assert (out["status"], out["sql"], out["attempts"], out["precheck_errors"]) == ("SQL_READY", OK_SQL, 1, [])


def test_generate_repairs_once():
    fake = Fake({"status": "OK", "sql": "SELECT AVG(current_salary) AS a FROM employees", "answer": "a"},
                {"status": "OK", "sql": OK_SQL, "answer": "b"})
    out = run(generate("재직 인원", SCHEMA, DEFAULT_FUNCTIONS, "enhanced", fake, S))
    assert out["attempts"] == 2 and out["sql"] == OK_SQL and out["precheck_errors"] == []
    assert "current_salary" in fake.calls[1][-1]["content"]  # 수리 요청에 이유 포함


def test_generate_gives_up_after_max_repairs():
    bad = {"status": "OK", "sql": "SELECT current_salary FROM employees", "answer": "a"}
    out = run(generate("q", SCHEMA, DEFAULT_FUNCTIONS, "enhanced", Fake(bad, bad), S))
    assert out["attempts"] == 2 and out["sql"] and out["precheck_errors"]  # 그대로 넘겨 Flask가 최종 거부


def test_generate_no_repair_when_disabled():
    bad = {"status": "OK", "sql": "SELECT current_salary FROM employees", "answer": "a"}
    out = run(generate("q", SCHEMA, DEFAULT_FUNCTIONS, "enhanced", Fake(bad), replace(S, max_repairs=0)))
    assert out["attempts"] == 1


@pytest.mark.parametrize("status,mapped", [("NEEDS_CLARIFICATION", "NEEDS_CLARIFICATION"), ("OUT_OF_SCOPE", "OUT_OF_SCOPE")])
def test_generate_non_sql(status, mapped):
    out = run(generate("q", SCHEMA, DEFAULT_FUNCTIONS, "enhanced", Fake({"status": status, "sql": None, "answer": "이유"}), S))
    assert (out["status"], out["sql"], out["answer"]) == (mapped, None, "이유")


def test_generate_unparseable_twice():
    out = run(generate("q", SCHEMA, DEFAULT_FUNCTIONS, "enhanced", Fake("음...", "몰라"), S))
    assert out["status"] == "GENERATION_FAILED" and out["sql"] is None and out["answer"]


def test_generate_blank_json_mode_reply_gets_one_repair():  # DeepSeek JSON 모드: JSON이 못 되면 빈 문자열
    out = run(generate("q", SCHEMA, DEFAULT_FUNCTIONS, "enhanced", Fake("", {"status": "OK", "sql": OK_SQL, "answer": "a"}), S))
    assert out["status"] == "SQL_READY" and out["attempts"] == 2


# ---------- 제공자 전용 옵션 (DeepSeek 생각 모드 끄기) ----------
def test_extra_body_merged_into_request(monkeypatch):
    from nl2sql.config import load_settings
    from nl2sql.llm import make_client
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_MODEL", "deepseek-flash")
    monkeypatch.setenv("LLM_JSON_MODE", "1")
    monkeypatch.setenv("LLM_EXTRA_BODY", '{"thinking":{"type":"disabled"}}')
    body = make_client(load_settings()).request_body([{"role": "user", "content": "q"}])
    assert body["thinking"] == {"type": "disabled"} and body["model"] == "deepseek-flash"
    assert body["temperature"] == 0 and body["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("raw", ['{"model":"x"}', '["thinking"]', '{"temperature":1}'])
def test_extra_body_rejects_reserved(monkeypatch, raw):
    from nl2sql.config import load_settings
    monkeypatch.setenv("LLM_EXTRA_BODY", raw)
    with pytest.raises(ValueError):
        load_settings()


def test_json_mode_prompt_mentions_json():  # DeepSeek JSON 모드 조건: 프롬프트에 'json' 단어
    for mode in ("simple", "enhanced"):
        assert "json" in build_messages(mode, "q", SCHEMA, DEFAULT_FUNCTIONS)[0]["content"].lower()


# ---------- 프롬프트: 두 방식 차이는 스키마 지식뿐 ----------
def test_prompt_simple_vs_enhanced():
    simple = build_messages("simple", "q", SCHEMA, DEFAULT_FUNCTIONS)[0]["content"]
    enh = build_messages("enhanced", "q", SCHEMA, DEFAULT_FUNCTIONS)[0]["content"]
    for common in ("TIMESTAMPDIFF", "company_id 조건은 쓰지 말 것", "[스키마]", "OUT_OF_SCOPE"):
        assert common in simple and common in enh
    for extra in ("[업무 용어", "ACTIVE(재직)", "[관계]", "[예시]", "장기근속자"):
        assert extra not in simple and extra in enh
    assert "vw_nl_org_headcounts" not in enh  # 스키마에 없는 테이블 설명은 안 넣음


# ---------- HTTP 계약 (Flask가 보내는 모양 그대로) ----------
@pytest.fixture()
def client():
    with TestClient(app) as c:
        app.state.settings = S
        yield c


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_queries_contract(client):
    app.state.client = Fake({"status": "OK", "sql": OK_SQL, "answer": "재직자 수"})
    r = client.post("/queries", json={"question": "재직 인원?", "conversation_id": None, "schema": SCHEMA, "functions": DEFAULT_FUNCTIONS})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "SQL_READY" and body["sql"] == OK_SQL and body["answer"] == "재직자 수"
    assert body["mode"] == "enhanced" and body["model"] == "fake-model"


def test_queries_mode_override(client):
    fake = Fake({"status": "OK", "sql": OK_SQL, "answer": "a"})
    app.state.client = fake
    assert client.post("/queries", json={"question": "q", "schema": SCHEMA, "mode": "simple"}).json()["mode"] == "simple"
    assert "[업무 용어" not in fake.calls[0][0]["content"]


def test_queries_not_configured(client):
    app.state.client = None
    assert client.post("/queries", json={"question": "q", "schema": SCHEMA}).status_code == 503


def test_queries_llm_timeout(client):
    app.state.client = Fake(LLMError("LLM_TIMEOUT", 504))
    r = client.post("/queries", json={"question": "q", "schema": SCHEMA})
    assert r.status_code == 504 and r.json()["detail"] == "LLM_TIMEOUT"


@pytest.mark.parametrize("payload", [{"question": "", "schema": SCHEMA}, {"question": "q"}, {"question": "x" * 501, "schema": SCHEMA},
                                     {"question": "q", "schema": {}}, {"question": "q", "schema": SCHEMA, "mode": "raw"}])
def test_queries_bad_input(client, payload):
    app.state.client = Fake()
    assert client.post("/queries", json=payload).status_code == 422


# ---------- Flask 쪽과 어긋나지 않는지 (백엔드 패키지 있을 때만) ----------
def _flask():
    pytest.importorskip("flask")
    sys.path.insert(0, str(BACKEND))
    from app.modules.ai import sql_policy
    return sql_policy


def test_default_functions_match_flask():
    assert DEFAULT_FUNCTIONS == sorted(_flask().SAFE_FUNCTIONS)


@pytest.mark.parametrize("sql", ["SELECT YEAR(hire_date) AS y FROM employees", "SELECT MONTH(hire_date) AS m FROM employees",
                                 "SELECT DAY(hire_date) AS d FROM employees", "SELECT DATE(hire_date) AS d FROM employees"])
def test_flask_policy_allows_declared_date_functions(sql):  # 수정 전엔 TS_OR_DS_TO_DATE 때문에 전부 거부
    out = _flask().validate_sql(sql, 1)
    import sqlglot
    sqlglot.parse_one(out, read="mysql")
    assert "company_id=1" in out.replace(" ", "")


@pytest.mark.parametrize("sql", ["SELECT NOW() AS n FROM employees", "SELECT AVG(current_salary) AS a FROM employees",
                                 "SELECT employee_name FROM employees WHERE hire_date >= DATE_SUB(CURRENT_DATE, INTERVAL 1 DAY)",
                                 "SELECT employee_name FROM employees WHERE employment_status = 'ACTIVE' AND SLEEP(5) = 0",
                                 "SELECT d.department_name FROM departments d WHERE EXISTS (SELECT current_salary FROM employees e)"])
def test_flask_policy_still_rejects(sql):
    with pytest.raises(ValueError):
        _flask().validate_sql(sql, 1)


LOGIC_SQL = [  # 수정 전엔 AND·OR·XOR·EXISTS가 '함수'로 분류돼 전부 거부됨 (실제 DeepSeek 호출에서 발견)
    "SELECT employee_name FROM employees WHERE employment_status = 'ACTIVE' AND YEAR(hire_date) = YEAR(CURRENT_DATE)",
    "SELECT employee_name FROM employees WHERE employment_status = 'ON_LEAVE' OR termination_date IS NOT NULL",
    "SELECT employee_name FROM employees WHERE job_id = 1 XOR job_id = 2",
    "SELECT d.department_name FROM departments d WHERE EXISTS (SELECT e.employee_id FROM employees e WHERE e.department_id = d.department_id)",
]


@pytest.mark.parametrize("sql", LOGIC_SQL)
def test_flask_policy_allows_logical_operators(sql):
    out = _flask().validate_sql(sql, 1)
    assert "company_id=1" in out.replace(" ", "")


@pytest.mark.parametrize("sql", LOGIC_SQL)
def test_precheck_allows_logical_operators(sql):
    assert precheck(sql, SCHEMA, DEFAULT_FUNCTIONS) == []


@pytest.mark.parametrize("sql,limit", [  # 전에는 무조건 LIMIT 200으로 덮어써서 '상위 N'·'가장 ~' 질문이 전체를 돌려줌
    ("SELECT employee_name FROM employees ORDER BY hire_date DESC LIMIT 1", 1),
    ("SELECT employee_name FROM employees ORDER BY hire_date DESC LIMIT 5", 5),
    ("SELECT employee_name FROM employees LIMIT 1000", 200),
    ("SELECT employee_name FROM employees LIMIT 1 + 1", 200),
    ("SELECT employee_name FROM employees", 200),
])
def test_flask_policy_limit(sql, limit):
    import sqlglot
    pol = _flask()
    assert pol.requested_limit(sqlglot.parse_one(pol.validate_sql(sql, 1), read="mysql")) == limit


def test_executor_probe_limit_and_percent_escape():
    _flask()
    from app.modules.ai.executor import with_probe_limit
    assert with_probe_limit("SELECT a FROM t LIMIT 5").endswith("LIMIT 5")      # 상위 N 유지
    assert with_probe_limit("SELECT a FROM t LIMIT 200").endswith("LIMIT 201")  # 기본 상한 → 잘림 확인용 201
    assert with_probe_limit("SELECT a FROM t").endswith("LIMIT 201")
    out = with_probe_limit("SELECT a AS `비율(%)` FROM t WHERE a LIKE '김%'")
    assert "LIKE '김%%'" in out and "`비율(%%)`" in out and out % () == out.replace("%%", "%")  # pymysql 치환 뒤 원래 SQL


def test_flask_and_precheck_agree_on_schema():
    pol = _flask()
    schema = {t: list(c) for t, c in pol.SAFE_TABLES.items()}
    for sql in ["SELECT employee_name FROM vw_nl_employee_directory WHERE job_title_name = '팀장'",
                "SELECT department_name, active_headcount FROM vw_nl_org_headcounts"]:
        assert precheck(sql, schema, sorted(pol.SAFE_FUNCTIONS)) == []
        pol.validate_sql(sql, 1)


def test_ai_reader_sql_grants_only_safe_columns(monkeypatch):
    _flask()
    monkeypatch.setenv("AI_DATABASE_URL", "mysql+pymysql://hris_ai:Abcdefghijklmnop_1234@mysql:3306/hris?charset=utf8mb4")
    monkeypatch.setenv("DB_USER", "hris_app")
    monkeypatch.setenv("DB_NAME", "hris")
    from app import create_app
    flask_app = create_app()
    out = flask_app.test_cli_runner().invoke(args=["ai-reader-sql"])
    assert out.exit_code == 0, out.output
    sql = out.output
    assert "GRANT SELECT (`employee_id`" in sql and "ON `hris`.`employees`" in sql
    for secret in ("current_salary", "phone", "email", "birth_date", "password_hash", "salary_history"):
        assert secret not in sql
    assert sql.count("GRANT SELECT") == len(_flask().SAFE_TABLES) and "ALL PRIVILEGES ON" not in sql
    monkeypatch.setenv("AI_DATABASE_URL", "mysql+pymysql://hris_app:Abcdefghijklmnop_1234@mysql:3306/hris")
    assert create_app().test_cli_runner().invoke(args=["ai-reader-sql"]).exit_code != 0  # 앱 계정 재사용 금지
