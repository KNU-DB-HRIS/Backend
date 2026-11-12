"""NL2SQL 생성 SQL 실행부 (읽기 전용 계정 · 5초 제한 · 최대 200행)

/api/v1/ai/queries 와 평가 하네스(ai/eval/run_eval.py)가 같은 경로로 실행하도록 routes.py에서 분리했다.
validate_sql()을 통과한 SQL만 넘겨야 한다.
"""
import sqlglot
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

MAX_ROWS = 200


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
            query_tree = sqlglot.parse_one(sql, read="mysql").limit(MAX_ROWS + 1)
            queried = conn.exec_driver_sql(query_tree.sql(dialect="mysql"))
            columns = list(queried.keys())
            rows = [list(row) for row in queried.fetchmany(MAX_ROWS + 1)]
        return columns, rows[:MAX_ROWS], len(rows) > MAX_ROWS
    finally:
        engine.dispose()
