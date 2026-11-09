#!/usr/bin/env bash
set -euo pipefail
umask 077

[[ $# -eq 0 ]] || { echo 'Usage: bash database-data.sh' >&2; exit 2; }
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

"$python_bin" -B - <<'PY' | docker compose exec -T backend flask --app wsgi:app db-seed-demo
import csv
import json
import os
import secrets
import sys
from pathlib import Path

path = Path('.seed-credentials.csv')
usernames = ['admin01'] + [f'employee{n:02d}' for n in range(2, 11)]
if not path.exists():
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(('username', 'password', 'role'))
        for username in usernames:
            role = 'HR_ADMIN' if username == 'admin01' else 'EMPLOYEE'
            writer.writerow((username, secrets.token_urlsafe(20), role))
with path.open(encoding='utf-8', newline='') as file:
    rows = list(csv.DictReader(file))
passwords = {row['username']: row['password'] for row in rows}
if set(passwords) != set(usernames) or len(rows) != 10 or any(len(p) < 12 for p in passwords.values()):
    sys.exit('Invalid credentials file. Refusing to seed with incomplete credentials.')
sys.stdout.write(json.dumps(passwords))
PY

printf '\nSample users: admin01, employee02 ... employee10\n'
printf 'Credentials: .seed-credentials.csv (keep private, never commit)\n'