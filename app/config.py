import os
from pathlib import Path

from sqlalchemy.engine import URL


def load_config():
    environment = os.getenv("APP_ENV", "development")
    if environment not in {"development", "production"}:
        raise ValueError("APP_ENV must be development or production")
    database_url = os.getenv("DATABASE_URL") or URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", os.getenv("MYSQL_USER", "hris_app")),
        password=os.getenv("DB_PASSWORD", os.getenv("MYSQL_PASSWORD", "")),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", os.getenv("MYSQL_DATABASE", "hris")),
        query={"charset": "utf8mb4"},
    )
    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    session_seconds = int(os.getenv("SESSION_IDLE_SECONDS", "7200"))
    if session_seconds <= 0:
        raise ValueError("SESSION_IDLE_SECONDS must be positive")
    return {
        "APP_ENV": environment,
        "DATABASE_URL": database_url,
        "SESSION_COOKIE_NAME": "hris_session",
        "SESSION_COOKIE_SECURE": environment == "production",
        "SESSION_IDLE_SECONDS": session_seconds,
        "CORS_ORIGINS": {origin.strip() for origin in origins.split(",") if origin.strip()},
        "STORAGE_DIR": Path(os.getenv("STORAGE_DIR", "instance/files")).resolve(),
        "AI_BASE_URL": os.getenv("AI_BASE_URL", ""),
        "AI_DATABASE_URL": os.getenv("AI_DATABASE_URL", ""),
        "AI_TIMEOUT_SECONDS": 20,
        "MAX_CONTENT_LENGTH": 3 * 1024 * 1024,
    }
