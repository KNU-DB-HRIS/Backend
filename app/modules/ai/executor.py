"""NL2SQL 생성 SQL 실행부 (읽기 전용 계정 · 5초 제한 · 최대 200행)

/api/v1/ai/queries 와 평가 하네스(ai/eval/run_eval.py)가 같은 경로로 실행하도록 routes.py에서 분리했다.
validate_sql()을 통과한 SQL만 넘겨야 한다.
"""
import sqlglot
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.modules.ai.sql_policy import requested_limit

MAX_ROWS = 200


def with_probe_limit(sql):
    """잘림 여부를 알려고 LIMIT 201로 실행. 단, 질문이 정한 더 작은 LIMIT(상위 N)은 그대로 둠"""
    tree = sqlglot.parse_one(sql, read="mysql")
    wanted = requested_limit(tree)
    if wanted is None or wanted >= MAX_ROWS:
        tree = tree.limit(MAX_ROWS + 1)
    # pymysql은 인자가 비어 있어도 SQL 문자열에 % 치환을 적용한다 → LIKE '김%'·별칭 `비율(%)`이
    # ValueError로 죽음(SQLAlchemyError가 아니라 500). 리터럴 %를 %%로 이스케이프
    return tree.sql(dialect="mysql").replace("%", "%%")


class ExecutorConfigError(Exception):
    """AI_DATABASE_URL이 없거나 안전 조건(전용 계정·pymysql)을 어김"""


def run_readonly(sql, database_url, forbidden_usernames=()):
    """(columns, rows, truncated) 반환. 설정 오류는 ExecutorConfigError, DB 오류는 SQLAlchemyError"""
    if not database_url:
        raise ExecutorConfigError("AI_DATABASE_URL is not set")
    url = make_url(database_url)
    if url.drivername != "mysql+pymysql" or url.username in {None, "root", *forbidden_usernames}:
        raise ExecutorConfigError("AI_DATABASE_URL must use a dedicated read-only account")
    engine = create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 3, "read_timeout": 7},
    )
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.exec_driver_sql("SET time_zone = '+09:00'")  # 메인 엔진과 같게: CURRENT_DATE를 KST 기준으로
            conn.exec_driver_sql("SET SESSION MAX_EXECUTION_TIME=5000")
            conn.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
            queried = conn.exec_driver_sql(with_probe_limit(sql))
            columns = list(queried.keys())
            rows = [list(row) for row in queried.fetchmany(MAX_ROWS + 1)]
        return columns, rows[:MAX_ROWS], len(rows) > MAX_ROWS
    finally:
        engine.dispose()
