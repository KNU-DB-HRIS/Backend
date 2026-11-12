import hashlib
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext

from app.db import all_rows, execute, insert, one, scalar, transaction
from app.security import create_account


def statements(source):
    delimiter, buffer = ";", ""
    for line in source.splitlines():
        if line.strip().upper().startswith("DELIMITER "):
            if buffer.strip():
                raise ValueError("Unexpected SQL before DELIMITER")
            delimiter = line.strip().split()[1]
            continue
        buffer += line + "\n"
        if buffer.rstrip().endswith(delimiter):
            yield buffer.rstrip()[: -len(delimiter)].strip()
            buffer = ""
    if buffer.strip():
        raise ValueError("Unterminated SQL statement")


@click.command("db-upgrade")
@click.option(
    "--base-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default="database",
    show_default=True,
)
@click.option("--baseline-existing", is_flag=True)
@with_appcontext
def db_upgrade(base_dir, baseline_existing):
    sql_files = sorted(base_dir.rglob("*.sql"), key=lambda path: (path.name, str(path)))
    base_files = [
        path
        for path in sql_files
        if path.name[:3].isdigit() and path.name[3:4] == "_" and 1 <= int(path.name[:3]) <= 14
    ]
    if [int(path.name[:3]) for path in base_files] != list(range(1, 15)):
        raise click.ClickException("Expected exactly one base SQL script for each of 001-014")
    names = [path.name for path in sql_files]
    if not {"015_api_contract.sql", "016_jwt_and_workflows.sql", "017_cookie_sessions.sql", "018_company_scoped_evaluations.sql"}.issubset(names):
        raise click.ClickException("Missing required SQL files 015-018 in database/")
    if len(names) != len(set(names)):
        raise click.ClickException("SQL filenames must be unique within database/")
    with (
        current_app.extensions["db"]
        .connect()
        .execution_options(isolation_level="AUTOCOMMIT") as conn
    ):
        lock = f"hris_migrate_{scalar(conn, 'SELECT DATABASE()')}"
        if scalar(conn, "SELECT GET_LOCK(:name, 10)", {"name": lock}) != 1:
            raise click.ClickException("Another migration process is running")
        try:
            tables = {
                row["TABLE_NAME"]
                for row in all_rows(
                    conn,
                    "SELECT TABLE_NAME FROM information_schema.tables "
                    "WHERE table_schema=DATABASE() AND table_type='BASE TABLE'",
                )
            }
            if tables and "schema_migrations" not in tables and not baseline_existing:
                raise click.ClickException(
                    "Existing schema found. Review it, then use --baseline-existing"
                )
            execute(
                conn,
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(name VARCHAR(200) PRIMARY KEY, sha256 CHAR(64) NOT NULL, "
                "applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6))",
            )
            for path in sql_files:
                source = path.read_text(encoding="utf-8-sig")
                checksum = hashlib.sha256(source.encode()).hexdigest()
                previous = one(
                    conn,
                    "SELECT sha256 FROM schema_migrations WHERE name=:name",
                    {"name": path.name},
                )
                if previous:
                    if previous["sha256"] != checksum:
                        raise click.ClickException(f"Applied migration changed: {path.name}")
                    click.echo(f"Skipped {path.name}")
                    continue
                if path.name == "018_company_scoped_evaluations.sql":
                    ambiguous = scalar(
                        conn,
                        "SELECT COUNT(*) FROM ("
                        "SELECT p.evaluation_period_id FROM evaluation_periods p "
                        "LEFT JOIN employee_evaluations v "
                        "ON v.evaluation_period_id=p.evaluation_period_id "
                        "LEFT JOIN employees e ON e.employee_id=v.employee_id "
                        "GROUP BY p.evaluation_period_id "
                        "HAVING COUNT(DISTINCT e.company_id)>1 OR "
                        "(COUNT(DISTINCT e.company_id)=0 AND (SELECT COUNT(*) FROM companies)<>1)"
                        ") ambiguous_periods",
                    )
                    if ambiguous:
                        raise click.ClickException(
                            "Legacy evaluation periods belong to multiple or unknown companies; "
                            "resolve ownership before applying migration 018"
                        )
                baseline = baseline_existing and path in base_files
                if not baseline:
                    for statement in statements(source):
                        conn.exec_driver_sql(statement)
                insert(conn, "schema_migrations", {"name": path.name, "sha256": checksum})
                click.echo(f"{'Baselined' if baseline else 'Applied'} {path.name}")
        finally:
            execute(conn, "SELECT RELEASE_LOCK(:name)", {"name": lock})


@click.command("create-user")
@click.option("--employee-id", type=click.IntRange(min=1), required=True)
@click.option("--username", required=True)
@click.option("--admin", is_flag=True)
@click.password_option(envvar="HRIS_USER_PASSWORD")
@with_appcontext
def create_user(employee_id, username, admin, password):
    if not 1 <= len(username) <= 50 or not 8 <= len(password) <= 128:
        raise click.ClickException("Username: 1-50 characters; password: 8-128 characters")
    with transaction() as conn:
        employee = one(
            conn,
            "SELECT employee_id FROM employees WHERE employee_id=:id "
            "AND employment_status IN ('ACTIVE','ON_LEAVE') FOR UPDATE",
            {"id": employee_id},
        )
        if not employee:
            raise click.ClickException("Active employee not found")
        if scalar(
            conn,
            "SELECT COUNT(*) FROM users WHERE username=:name OR employee_id=:id",
            {"name": username, "id": employee_id},
        ):
            raise click.ClickException("Username or employee account already exists")
        role_code = "HR_ADMIN" if admin else "EMPLOYEE"
        execute(
            conn,
            "INSERT INTO roles(role_code,role_name,is_active) VALUES(:code,:name,1) "
            "ON DUPLICATE KEY UPDATE role_code=VALUES(role_code)",
            {"code": role_code, "name": "HR 관리자" if admin else "사원"},
        )
        role = one(
            conn,
            "SELECT role_id,is_active FROM roles WHERE role_code=:code FOR UPDATE",
            {"code": role_code},
        )
        if not role["is_active"]:
            raise click.ClickException("Role is inactive")
        user_id = create_account(conn, employee_id, username, password, role["role_id"])
        click.echo(f"Created user {user_id}")


def register_commands(app):
    from app.seed_demo import db_seed_demo

    app.cli.add_command(db_upgrade)
    app.cli.add_command(create_user)
    app.cli.add_command(db_seed_demo)
    app.cli.add_command(ai_reader_sql)


@click.command("ai-reader-sql")
@with_appcontext
def ai_reader_sql():
    """NL2SQL 전용 읽기 계정 SQL을 출력 (root로 실행: setup/ai.sh 가 mysql 컨테이너에 파이프)

    계정·비밀번호는 AI_DATABASE_URL에서 읽고, 권한은 sql_policy.SAFE_TABLES의 열에만 SELECT를 준다.
    검증기를 우회하는 SQL이 와도 급여·연락처 같은 열은 DB 권한 단계에서 막힌다.
    """
    import re

    from sqlalchemy.engine import make_url

    from app.modules.ai.sql_policy import SAFE_TABLES

    url = make_url(current_app.config["AI_DATABASE_URL"] or "")
    app_user = current_app.extensions["db"].url.username
    database = current_app.extensions["db"].url.database
    ident = re.compile(r"^[A-Za-z0-9_]{1,32}$")
    if url.drivername != "mysql+pymysql" or not url.username or url.username in {"root", app_user}:
        raise click.ClickException("AI_DATABASE_URL must name a dedicated mysql+pymysql account")
    if not ident.match(url.username) or not ident.match(database or ""):
        raise click.ClickException("Unexpected characters in AI account or database name")
    if not url.password or not re.fullmatch(r"[A-Za-z0-9_\-]{16,128}", url.password):
        raise click.ClickException("AI account password must be 16-128 URL-safe characters")
    if url.database != database:
        raise click.ClickException("AI_DATABASE_URL must point at the application database")
    account = f"'{url.username}'@'%'"
    lines = [
        f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY '{url.password}';",
        f"ALTER USER {account} IDENTIFIED BY '{url.password}' WITH MAX_USER_CONNECTIONS 5;",
        f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM {account};",
    ]
    for table, columns in SAFE_TABLES.items():
        if not ident.match(table) or not all(ident.match(c) for c in columns):
            raise click.ClickException(f"Unexpected identifier in SAFE_TABLES: {table}")
        cols = ", ".join(f"`{c}`" for c in columns)
        lines.append(f"GRANT SELECT ({cols}) ON `{database}`.`{table}` TO {account};")
    click.echo("\n".join(lines))
