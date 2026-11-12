import sqlglot
from sqlglot import exp

SAFE_TABLES = {
    "employees": (
        "employee_id",
        "company_id",
        "employee_no",
        "employee_name",
        "hire_date",
        "termination_date",
        "employment_type",
        "employment_status",
        "department_id",
        "position_id",
        "job_id",
        "job_title_id",
    ),
    "departments": (
        "department_id",
        "company_id",
        "parent_department_id",
        "department_code",
        "department_name",
        "is_active",
    ),
    "positions": (
        "position_id",
        "company_id",
        "position_code",
        "position_name",
        "position_level",
        "is_active",
    ),
    "jobs": (
        "job_id",
        "company_id",
        "job_code",
        "job_name",
        "job_category",
        "job_family",
        "is_active",
    ),
    "job_titles": ("job_title_id", "company_id", "job_title_code", "job_title_name", "is_active"),
    "vw_nl_employee_directory": (
        "employee_id",
        "company_id",
        "employee_no",
        "employee_name",
        "hire_date",
        "employment_status",
        "department_name",
        "position_name",
        "job_name",
        "job_title_name",
    ),
    "vw_nl_org_headcounts": ("company_id", "department_id", "department_name", "active_headcount"),
}
SAFE_FUNCTIONS = {
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "COALESCE",
    "ROUND",
    "ABS",
    "FLOOR",
    "CEIL",
    "DATE",
    "YEAR",
    "MONTH",
    "DAY",
    "DATEDIFF",
    "TIMESTAMPDIFF",
    "LOWER",
    "UPPER",
    "CONCAT",
    "NULLIF",
    "CAST",
    "IF",
    "CASE",
    "CURRENT_DATE",
    "EXTRACT",
}
# sqlglot(MySQL)가 YEAR/MONTH/DAY/DATE(x) 를 읽을 때 인자를 TS_OR_DS_TO_DATE(x)로 감싸서 넣는 내부 노드.
# 사용자가 쓴 함수가 아니라 파서가 끼운 날짜 변환이라 허용 (없으면 위의 YEAR·MONTH·DAY·DATE가 전부 거부됨)
IMPLICIT_FUNCTIONS = {"TS_OR_DS_TO_DATE"}
# sqlglot는 논리 연산자 AND·OR·XOR와 EXISTS도 Func 하위 클래스로 만든다 → 함수 검사에서 제외
# (없으면 WHERE 조건이 둘 이상인 SQL이 전부 거부됨. EXISTS 안 서브쿼리의 테이블·열 검사는 그대로 적용)
OPERATOR_NODES = (exp.Connector, exp.Exists)


MAX_LIMIT = 200


def requested_limit(tree):
    """SQL에 적힌 LIMIT n (정수 리터럴일 때만). 없거나 식이면 None"""
    node = tree.args.get("limit")
    value = node.args.get("expression") if node is not None else None
    if isinstance(value, exp.Literal) and not value.is_string and value.this.isdigit():
        return int(value.this)
    return None


def validate_sql(sql, company_id):
    if (
        not isinstance(sql, str)
        or len(sql) > 10000
        or any(marker in sql for marker in ("/*", "--", "#"))
    ):
        raise ValueError("SQL rejected")
    statements = sqlglot.parse(sql, read="mysql")
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("A single SELECT is required")
    tree = statements[0]
    if tree.args.get("with_") or any(
        isinstance(n, (exp.Into, exp.Lock, exp.Parameter, exp.SessionParameter, exp.Command))
        for n in tree.walk()
    ):
        raise ValueError("SQL operation is not allowed")
    if any(
        isinstance(n, exp.Func)
        and not isinstance(n, OPERATOR_NODES)
        and n.sql_name() not in SAFE_FUNCTIONS | IMPLICIT_FUNCTIONS
        for n in tree.walk()
    ):
        raise ValueError("Function is not allowed")
    tables = list(tree.find_all(exp.Table))
    if not tables or len(tables) > 8:
        raise ValueError("Table is required")
    for table in tables:
        if table.name not in SAFE_TABLES or table.db or table.catalog:
            raise ValueError("Table is not allowed")
    allowed_columns = {column for table in tables for column in SAFE_TABLES[table.name]}
    allowed_columns.update(node.alias for node in tree.find_all(exp.Alias))
    for column in tree.find_all(exp.Column):
        if column.name not in allowed_columns:
            raise ValueError("Column is not allowed")
    for star in tree.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count):
            raise ValueError("Explicit columns are required")
    for table in tables:
        alias = table.alias_or_name
        selected = ",".join(SAFE_TABLES[table.name])
        scoped = sqlglot.parse_one(
            f"SELECT {selected} FROM {table.name} WHERE company_id={int(company_id)}", read="mysql"
        )
        table.replace(scoped.subquery(alias=alias))
    # '상위 5명'처럼 질문이 정한 LIMIT(1~200)은 유지, 없거나 크거나 식이면 200으로 고정
    # (전에는 무조건 200으로 덮어써서 '가장 최근 1명' 같은 질문이 전체 목록을 돌려줌)
    wanted = requested_limit(tree)
    limit = wanted if wanted is not None and 1 <= wanted <= MAX_LIMIT else MAX_LIMIT
    tree.set("limit", exp.Limit(expression=exp.Literal.number(limit)))
    if tree.args.get("offset"):
        raise ValueError("OFFSET is not allowed")
    return tree.sql(dialect="mysql")
