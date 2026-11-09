import re
from datetime import date

from flask import request

from app.errors import ApiError


def invalid(field):
    raise ApiError("VALIDATION_ERROR", details={"field": field})


def string(value, field, maximum=100, nullable=False, minimum=1):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        invalid(field)
    return value.strip()


def integer(value, field, minimum=1, maximum=2147483647, nullable=False):
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        invalid(field)
    return value


def boolean(value, field):
    if not isinstance(value, bool):
        invalid(field)
    return value


def enum(value, field, choices):
    if value not in choices:
        invalid(field)
    return value


def iso_date(value, field, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        invalid(field)
    try:
        return date.fromisoformat(value)
    except ValueError:
        invalid(field)


def email(value, field="email", nullable=False):
    result = string(value, field, 100, nullable)
    if result is not None and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", result):
        invalid(field)
    return result


def body(fields, required=(), readonly=(), strict=True):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        invalid("body")
    missing = set(required) - data.keys()
    if missing:
        invalid(sorted(missing)[0])
    extra = data.keys() - fields.keys() - set(readonly)
    if extra and strict:
        raise ApiError("FIELD_NOT_EDITABLE", details={"field": sorted(extra)[0]})
    return {key: fields[key](value, key) for key, value in data.items() if key in fields}


def text_field(maximum=100, nullable=False):
    return lambda value, key: string(value, key, maximum, nullable)


def int_field(minimum=1, maximum=2147483647, nullable=False):
    return lambda value, key: integer(value, key, minimum, maximum, nullable)


def date_field(nullable=False):
    return lambda value, key: iso_date(value, key, nullable)


def choice_field(*choices):
    return lambda value, key: enum(value, key, choices)


def query_int(key, default=None, maximum=2147483647):
    value = request.args.get(key)
    if value is None:
        return default
    if not re.fullmatch(r"[0-9]+", value):
        invalid(key)
    return integer(int(value), key, maximum=maximum)


def query_text(key="q", required=False, maximum=50):
    value = request.args.get(key)
    if value is None and not required:
        return None
    return string(value, key, maximum)


def query_choice(key, choices, default=None):
    value = request.args.get(key, default)
    return enum(value, key, choices) if value is not None else None


def query_bool(key, default=False):
    value = request.args.get(key)
    if value is None:
        return default
    if value not in {"true", "false"}:
        invalid(key)
    return value == "true"


def pagination(default_size=20):
    return query_int("page", 1), query_int("size", default_size, 100)


def page_result(items, page, size, total=None):
    if total is None:
        total = len(items)
        items = items[(page - 1) * size : page * size]
    return {"items": items, "page": page, "size": size, "total": total}


def like(value):
    return "%" + value.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
