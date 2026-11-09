from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from flask import current_app, g, has_request_context
from flask.json.provider import DefaultJSONProvider
from sqlalchemy import create_engine, event, text

from app.validation import page_result

KST = ZoneInfo("Asia/Seoul")


def now():
    return datetime.now(KST).replace(tzinfo=None)


def today():
    return now().date()


class JSONProvider(DefaultJSONProvider):
    ensure_ascii = False

    @staticmethod
    def default(value):
        if isinstance(value, datetime):
            return (
                value.replace(tzinfo=KST).isoformat() if value.tzinfo is None else value.isoformat()
            )
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return int(value) if value == value.to_integral_value() else float(value)
        return DefaultJSONProvider.default(value)


def init_db(app):
    engine = create_engine(
        app.config["DATABASE_URL"],
        pool_pre_ping=True,
        pool_recycle=1800,
        hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def initialize_connection(connection, record):
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+09:00'")
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")

    @event.listens_for(engine, "reset")
    def reset_connection(connection, record, state):
        if not state.terminate_only:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET @hris_actor_user_id = NULL, @hris_actor_ip_address = NULL")
            except Exception:
                record.invalidate()

    app.extensions["db"] = engine


def execute(connection, sql, params=None):
    return connection.execute(text(sql), params or {})


def one(connection, sql, params=None):
    result = execute(connection, sql, params).mappings().first()
    return dict(result) if result is not None else None


def all_rows(connection, sql, params=None):
    return [dict(row) for row in execute(connection, sql, params).mappings()]


def scalar(connection, sql, params=None):
    return execute(connection, sql, params).scalar()


def page_query(connection, fields, source, params, order, page, size):
    total = scalar(connection, f"SELECT COUNT(*) {source}", params)
    rows = all_rows(
        connection,
        f"SELECT {fields} {source} ORDER BY {order} LIMIT :size OFFSET :offset",
        {**params, "size": size, "offset": (page - 1) * size},
    )
    return page_result(rows, page, size, total)


@contextmanager
def transaction():
    with current_app.extensions["db"].begin() as connection:
        if has_request_context() and getattr(g, "actor", None):
            execute(
                connection,
                "SET @hris_actor_user_id=:user, @hris_actor_ip_address=:ip",
                {"user": g.actor["user_id"], "ip": g.actor.get("ip")},
            )
        yield connection


def insert(connection, table, values):
    keys = list(values)
    result = execute(
        connection,
        f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join(':' + key for key in keys)})",
        values,
    )
    return result.lastrowid


def update(connection, table, key, identifier, values):
    if values:
        execute(
            connection,
            f"UPDATE {table} SET "
            + ", ".join(f"{k}=:{k}" for k in values)
            + f" WHERE {key}=:target_id",
            {**values, "target_id": identifier},
        )


def audit(connection, action, resource, resource_id=None):
    actor = g.actor
    insert(
        connection,
        "audit_logs",
        {
            "user_id": actor["user_id"],
            "company_id": actor["company_id"],
            "action_type": action,
            "resource_type": resource,
            "resource_id": resource_id,
            "ip_address": actor.get("ip"),
        },
    )


def lock_company(connection, company_id):
    return one(
        connection,
        "SELECT company_id FROM companies WHERE company_id=:id FOR UPDATE",
        {"id": company_id},
    )
