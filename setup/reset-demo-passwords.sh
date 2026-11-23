#!/usr/bin/env bash
# 샘플 계정 10개(admin01, employee02 ~ employee10)의 비밀번호를 새로 만들어 DB에 반영하고
# .seed-credentials.csv를 새 비밀번호로 다시 쓴다. 비밀번호를 잊었거나 파일을 잃어버렸을 때 사용.
# 데이터는 그대로 두고 비밀번호만 바꾸며, 해당 계정의 기존 로그인은 모두 끊긴다.
set -euo pipefail
umask 077

[[ $# -eq 0 ]] || { echo 'Usage: bash ./setup/reset-demo-passwords.sh' >&2; exit 2; }
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT_DIR"
[[ -f .env ]] || { echo 'Missing .env. Run bash setup.sh first.' >&2; exit 2; }
command -v docker >/dev/null || { echo 'Docker is required.' >&2; exit 2; }
python_bin="${PYTHON_BIN:-python}"
command -v "$python_bin" >/dev/null || python_bin=python3
command -v "$python_bin" >/dev/null || { echo 'Python 3 is required.' >&2; exit 2; }
docker compose ps --status running --services | grep -Fxq backend || {
    echo 'Backend is not running. Run bash setup.sh first.' >&2
    exit 2
}

# 새 비밀번호는 임시 파일에 먼저 쓰고, DB 반영이 성공한 뒤에만 .seed-credentials.csv로 바꾼다
tmp="$(mktemp ./.seed-credentials.new.XXXXXX)"
trap 'rm -f "$tmp"' EXIT

"$python_bin" -B - "$tmp" <<'PY' | docker compose exec -T backend flask --app wsgi:app reset-passwords
import csv
import json
import secrets
import sys

usernames = ['admin01'] + [f'employee{n:02d}' for n in range(2, 11)]
rows = [(name, secrets.token_urlsafe(20), 'HR_ADMIN' if name == 'admin01' else 'EMPLOYEE') for name in usernames]
with open(sys.argv[1], 'w', encoding='utf-8', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(('username', 'password', 'role'))
    writer.writerows(rows)
sys.stdout.write(json.dumps({name: password for name, password, _ in rows}))
PY

mv -f "$tmp" .seed-credentials.csv
chmod 600 .seed-credentials.csv
trap - EXIT
printf '\nNew passwords: .seed-credentials.csv (admin01, employee02 ... employee10). Keep private, never commit.\n'
