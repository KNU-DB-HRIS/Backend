"""채점 로직 단위 테스트"""
import datetime as dt
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from scoring import same_result, verdict  # noqa: E402

ROWS = {"type": "rows"}


def test_same_result_ignores_row_and_column_order_and_extra_columns():
    gold = [("개발팀", 3), ("인사팀", 2)]
    assert same_result(gold, [(2, "인사팀"), (3, "개발팀")])
    assert same_result(gold, [(1, "인사팀", 2), (2, "개발팀", 3)])  # 열이 더 있어도 정답 열 포함이면 OK
    assert not same_result(gold, [("개발팀", 3)])
    assert not same_result(gold, [("개발팀", 3), ("인사팀", 3)])


def test_same_result_ordered():
    gold = [("부장",), ("차장",), ("과장",)]
    assert same_result(gold, [("부장",), ("차장",), ("과장",)], ordered=True)
    assert not same_result(gold, [("과장",), ("차장",), ("부장",)], ordered=True)
    assert same_result(gold, [("과장",), ("차장",), ("부장",)], ordered=False)


def test_normalization():
    assert same_result([(Decimal("4.333333"),)], [(4.33,)])
    assert same_result([(9,)], [(Decimal("9"),)])
    assert same_result([(dt.date(2026, 1, 3),)], [("2026-01-03",)])
    assert same_result([], [])
    assert not same_result([], [(1,)])


def test_verdicts():
    q = {"expect": ROWS}
    assert verdict(q, "SQL_READY", "S", None, None, [(1,)], [(1,)]) == "CORRECT"
    assert verdict(q, "SQL_READY", "S", None, None, [(1,)], [(2,)]) == "WRONG_RESULT"
    assert verdict(q, "SQL_READY", "S", "Column is not allowed", None, [(1,)], None) == "REJECTED"
    assert verdict(q, "SQL_READY", "S", None, "OperationalError", [(1,)], None) == "EXEC_ERROR"
    assert verdict(q, "GENERATION_FAILED", None, None, None, [(1,)], None) == "NO_SQL"
    assert verdict(q, "NEEDS_CLARIFICATION", None, None, None, [(1,)], None) == "UNEXPECTED_STATUS"
    assert verdict(q, "AI_ERROR", None, None, None, [(1,)], None) == "AI_ERROR"
    oos = {"expect": {"type": "status", "status": "OUT_OF_SCOPE"}}
    assert verdict(oos, "OUT_OF_SCOPE", None, None, None, None, None) == "CORRECT"
    assert verdict(oos, "SQL_READY", "SELECT AVG(current_salary)", "Column is not allowed", None, None, None) == "BLOCKED_BY_SERVER"
    assert verdict(oos, "SQL_READY", "SELECT AVG(position_level)", None, None, None, [(2.4,)]) == "WRONG_RESULT"
    assert verdict(oos, "NEEDS_CLARIFICATION", None, None, None, None, None) == "UNEXPECTED_STATUS"
