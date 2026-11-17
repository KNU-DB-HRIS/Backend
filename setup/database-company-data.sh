#!/usr/bin/env bash
# 계열사 샘플 데이터 (개발용): 이미 만든 빈 회사에 부서 5개, 직원 N명, 급여, 근태, 평가, 결재, 일정을 넣는다
# usage: bash ./setup/database-company-data.sh <company_id> [직원 수=20] [계정 접두어=media]
# 계정 3개(인사관리자 1, 사원 2)의 비밀번호는 .seed-credentials-<접두어>.csv 에 저장 (공유 금지, Git 제외)
set -euo pipefail
umask 077

[[ $# -ge 1 && $# -le 3 ]] || { echo 'Usage: bash ./setup/database-company-data.sh <company_id> [size=20] [prefix=media]' >&2; exit 2; }
COMPANY_ID="$1"; SIZE="${2:-20}"; PREFIX="${3:-media}"
[[ "$COMPANY_ID" =~ ^[0-9]+$ && "$SIZE" =~ ^[0-9]+$ && "$PREFIX" =~ ^[A-Za-z0-9]{1,20}$ ]] || {
    echo 'company_id and size must be numbers, prefix must be 1-20 letters/digits' >&2; exit 2; }
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT_DIR"
[[ -f .env ]] || { echo 'Missing .env. Run bash ./setup/setup.sh first.' >&2; exit 2; }
command -v docker >/dev/null || { echo 'Docker is required.' >&2; exit 2; }
python_bin="${PYTHON_BIN:-python}"
command -v "$python_bin" >/dev/null || python_bin=python3
command -v "$python_bin" >/dev/null || { echo 'Python 3 is required.' >&2; exit 2; }
docker compose ps --status running --services | grep -Fxq backend || {
    echo 'Backend is not running. Run bash ./setup/setup.sh first.' >&2; exit 2; }

PREFIX="$PREFIX" "$python_bin" -B - <<'PY' | docker compose exec -T backend flask --app wsgi:app db-seed-company --company-id "$COMPANY_ID" --size "$SIZE" --prefix "$PREFIX"
import csv
import json
import os
import secrets
import sys
from pathlib import Path

prefix = os.environ['PREFIX']
usernames = [f'{prefix}{n:02d}' for n in (1, 2, 3)]
path = Path(f'.seed-credentials-{prefix}.csv')
if not path.exists():
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(('username', 'password', 'role'))
        for username in usernames:
            writer.writerow((username, secrets.token_urlsafe(20), 'HR_ADMIN' if username.endswith('01') else 'EMPLOYEE'))
with path.open(encoding='utf-8', newline='') as file:
    passwords = {row['username']: row['password'] for row in csv.DictReader(file)}
if set(passwords) != set(usernames):
    sys.exit(f'Invalid credentials file {path}. Delete it or use another prefix.')
sys.stdout.write(json.dumps(passwords))
PY

printf '\nAccounts: %s01 (HR_ADMIN), %s02, %s03\n' "$PREFIX" "$PREFIX" "$PREFIX"
printf 'Credentials: .seed-credentials-%s.csv (keep private, never commit)\n' "$PREFIX"
