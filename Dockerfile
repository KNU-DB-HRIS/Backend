FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-nanum \
    && rm -rf /var/lib/apt/lists/* \
    && pip install -r requirements.txt \
    && groupadd --system hris \
    && useradd --system --gid hris --home-dir /app hris

COPY --chown=hris:hris app /app/app
COPY --chown=hris:hris config /app/config
COPY --chown=hris:hris wsgi.py /app/wsgi.py
RUN mkdir -p /app/instance/files \
    && chown -R hris:hris /app/instance

USER hris
EXPOSE 5000
CMD ["gunicorn", "--config", "config/gunicorn.conf.py", "wsgi:app"]
