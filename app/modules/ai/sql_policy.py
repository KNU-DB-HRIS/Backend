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
    if any(isinstance(n, exp.Func) and n.sql_name() not in SAFE_FUNCTIONS for n in tree.walk()):
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
    tree.set("limit", exp.Limit(expression=exp.Literal.number(200)))
    if tree.args.get("offset"):
        raise ValueError("OFFSET is not allowed")
    return tree.sql(dialect="mysql")
