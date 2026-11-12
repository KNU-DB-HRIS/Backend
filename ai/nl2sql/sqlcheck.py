"""LLM 출력 파싱 + 사전 점검

사전 점검은 Flask sql_policy.validate_sql과 같은 규칙(회사 범위 주입만 뺌)으로 걸러서,
걸리면 LLM에게 1회 고쳐 달라고 한다. 최종 판단은 언제나 Flask 검증기 + DB 권한.
"""
import json
import re

import sqlglot
from sqlglot import exp

IMPLICIT_FUNCTIONS = {"TS_OR_DS_TO_DATE"}  # sqlglot가 YEAR/MONTH/DAY/DATE 인자에 끼우는 내부 노드
STATUSES = {"OK", "NEEDS_CLARIFICATION", "OUT_OF_SCOPE"}
_FENCE = re.compile(r"```(?:json|sql)?\s*(.*?)```", re.S | re.I)


class UnparseableOutput(Exception):
    pass


def parse_output(raw: str) -> dict:
    """LLM 텍스트 → {status, sql, answer}. JSON이 기본, 코드 블록 SQL만 온 경우도 받아줌"""
    text = raw.strip()
    candidates = [m.group(1).strip() for m in _FENCE.finditer(text)] + [text]
    for c in candidates:
        i, j = c.find("{"), c.rfind("}")
        if i == -1 or j <= i:
            continue
        try:
            obj = json.loads(c[i:j + 1])
        except ValueError:
            continue
        if isinstance(obj, dict):
            status = obj.get("status") if obj.get("status") in STATUSES else ("OK" if obj.get("sql") else None)
            if status is None:
                continue
            raw_sql = obj.get("sql")
            sql = raw_sql.strip() if isinstance(raw_sql, str) and raw_sql.strip() else None
            answer = obj.get("answer") if isinstance(obj.get("answer"), str) else None
            if status == "OK" and not sql:
                raise UnparseableOutput("status OK without sql")
            return {"status": status, "sql": sql if status == "OK" else None, "answer": answer}
    for c in candidates:  # JSON이 아니면 SELECT 문 자체를 찾음
        m = re.search(r"\bSELECT\b.*", c, re.S | re.I)
        if m:
            return {"status": "OK", "sql": m.group(0).strip(), "answer": None}
    raise UnparseableOutput("no JSON or SELECT in model output")


def clean_sql(sql: str) -> str:
    """세미콜론·주석 제거. 주석이 있으면 sqlglot로 다시 써서 없앰(Flask는 주석 표식이 하나라도 있으면 거부)"""
    s = sql.strip().rstrip(";").strip()
    if any(m in s for m in ("--", "/*", "#")):
        try:
            s = sqlglot.parse_one(s, read="mysql").sql(dialect="mysql", comments=False)
        except sqlglot.errors.SqlglotError:
            pass
    return s


def precheck(sql: str, schema: dict[str, list[str]], functions: list[str]) -> list[str]:
    problems = []
    if any(m in sql for m in ("--", "/*", "#")):
        problems.append("주석 표식(--, /*, #) 금지")
    try:
        statements = sqlglot.parse(sql, read="mysql")
    except sqlglot.errors.SqlglotError as e:
        return problems + [f"SQL 문법 오류: {str(e).splitlines()[0][:160]}"]
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        return problems + ["SELECT 한 문장만 (UNION·여러 문장 금지)"]
    tree = statements[0]
    if tree.args.get("with_") or tree.args.get("with"):
        problems.append("WITH(CTE) 금지")
    if any(isinstance(n, (exp.Into, exp.Lock, exp.Parameter, exp.SessionParameter, exp.Command)) for n in tree.walk()):
        problems.append("허용되지 않은 구문")
    allowed_funcs = set(functions) | IMPLICIT_FUNCTIONS
    bad = sorted({n.sql_name() for n in tree.walk() if isinstance(n, exp.Func) and n.sql_name() not in allowed_funcs})
    if bad:
        problems.append("허용되지 않은 함수: " + ", ".join("NOW 같은 사용자 함수" if b == "ANONYMOUS" else b for b in bad))
    tables = list(tree.find_all(exp.Table))
    if not tables:
        problems.append("FROM 테이블 필요")
    unknown = sorted({t.name for t in tables if t.name not in schema or t.db or t.catalog})
    if unknown:
        problems.append("없는 테이블: " + ", ".join(unknown))
    allowed_cols = {c for t in tables if t.name in schema for c in schema[t.name]}
    allowed_cols |= {a.alias for a in tree.find_all(exp.Alias)}
    bad_cols = sorted({c.name for c in tree.find_all(exp.Column) if c.name not in allowed_cols})
    if bad_cols:
        problems.append("쓸 수 없는 열: " + ", ".join(bad_cols))
    if any(not isinstance(s.parent, exp.Count) for s in tree.find_all(exp.Star)):
        problems.append("SELECT * 금지, 열 이름을 적을 것")
    if tree.args.get("offset"):
        problems.append("OFFSET 금지")
    return problems
