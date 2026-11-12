#!/usr/bin/env bash
# HR AI(NL2SQL) 준비: 읽기 전용 DB 계정(hris_ai) 생성·권한 갱신 + ai 서비스 기동
# setup.sh가 마지막에 자동 실행. SAFE_TABLES를 바꾼 뒤 권한만 다시 맞출 때도 이것만 실행
set -euo pipefail
umask 077

[[ $# -eq 0 ]] || { echo 'Usage: bash ./setup/ai.sh' >&2; exit 2; }
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT_DIR"
[[ -f .env ]] || { echo 'Missing .env. Run bash ./setup/setup.sh first.' >&2; exit 2; }
command -v docker >/dev/null || { echo 'Docker is required.' >&2; exit 2; }
grep -Eq '^AI_DATABASE_URL=mysql\+pymysql://.+' .env || {
    echo 'AI_DATABASE_URL is empty. Run bash ./setup/setup.sh once (it generates the read-only account URL).' >&2
    exit 2
}

docker compose config --quiet
docker compose up -d --wait --wait-timeout 180 mysql
# 권한 SQL은 Flask가 sql_policy.SAFE_TABLES로 만들고(열 단위 SELECT만), root로 적용
docker compose run --rm --no-deps -T backend flask --app wsgi:app ai-reader-sql \
    | docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot'
docker compose up -d --build --wait --wait-timeout 180 ai backend

port="$(sed -n 's/^AI_PORT=//p' .env | tail -1)"
printf 'HR AI ready. Read-only account applied.\n'
printf 'AI health: http://localhost:%s/health\n' "${port:-8001}"
grep -Eq '^(LLM_MODEL=.+|LLM_FIXTURE_FILE=.+)' .env || printf 'LLM is not configured yet: set LLM_BASE_URL, LLM_MODEL, LLM_API_KEY in .env, then rerun this script.\n'
