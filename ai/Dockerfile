FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt \
    && groupadd --system nl2sql \
    && useradd --system --gid nl2sql --home-dir /app nl2sql

COPY --chown=nl2sql:nl2sql nl2sql /app/nl2sql
COPY --chown=nl2sql:nl2sql eval/fixtures /app/fixtures

USER nl2sql
EXPOSE 8000
CMD ["uvicorn", "nl2sql.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log"]
