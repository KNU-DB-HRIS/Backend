"""채점 로직 (DB·네트워크 없음 → 단위 테스트 대상)

정답 판정 = 실행 결과 비교(execution accuracy).
- 값 정규화: Decimal/float → 소수 둘째 자리, 날짜 → ISO 문자열
- 생성 SQL이 열을 더 많이 골라도 정답 열을 모두 포함하면(열 순서 무관) 같은 결과로 봄
- order=True 인 질문만 행 순서까지 비교, 나머지는 행 집합(중복 포함) 비교
"""
import datetime as dt
import itertools
from collections import Counter
from decimal import Decimal

VERDICTS = ("CORRECT", "WRONG_RESULT", "EXEC_ERROR", "REJECTED", "NO_SQL", "UNEXPECTED_STATUS", "BLOCKED_BY_SERVER", "AI_ERROR")


def norm(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, Decimal):
        v = float(v)
    if isinstance(v, float):
        return round(v, 2)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    if isinstance(v, str):
        return v.strip()
    return v


def norm_rows(rows):
    return [tuple(norm(v) for v in r) for r in rows]


def same_result(gold_rows, gen_rows, ordered=False, max_width=12):
    gold, gen = norm_rows(gold_rows), norm_rows(gen_rows)
    if len(gold) != len(gen):
        return False
    if not gold:
        return True
    gw, nw = len(gold[0]), len(gen[0])
    if gw > nw or nw > max_width:
        return False
    for cols in itertools.permutations(range(nw), gw):
        proj = [tuple(r[i] for i in cols) for r in gen]
        if (proj == gold) if ordered else (Counter(proj) == Counter(gold)):
            return True
    return False


def verdict(question, ai_status, gen_sql, rejected, exec_error, gold_rows, gen_rows):
    """question.expect = {"type": "rows", "order": bool} | {"type": "status", "status": "..."}"""
    exp = question["expect"]
    if ai_status == "AI_ERROR":
        return "AI_ERROR"
    if exp["type"] == "status":
        if ai_status == exp["status"]:
            return "CORRECT"
        if gen_sql and rejected:
            return "BLOCKED_BY_SERVER"  # 거절해야 할 질문에 SQL을 만들었지만 서버가 막음(안전하지만 오답)
        return "UNEXPECTED_STATUS" if not gen_sql else "WRONG_RESULT"
    if ai_status in ("NEEDS_CLARIFICATION", "OUT_OF_SCOPE"):
        return "UNEXPECTED_STATUS"
    if not gen_sql:
        return "NO_SQL"
    if rejected:
        return "REJECTED"
    if exec_error:
        return "EXEC_ERROR"
    return "CORRECT" if same_result(gold_rows, gen_rows, exp.get("order", False)) else "WRONG_RESULT"
