#!/usr/bin/env bash
set -euo pipefail
umask 077

[[ $# -eq 0 ]] || { echo 'Usage: bash ./setup/setup.sh' >&2; exit 2; }
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT_DIR"
command -v docker >/dev/null || { echo 'Docker and Docker Compose are required.' >&2; exit 2; }
docker compose version >/dev/null
docker info >/dev/null 2>&1 || { echo 'Start Docker Desktop or Docker Engine first.' >&2; exit 2; }
python_bin="${PYTHON_BIN:-python}"
command -v "$python_bin" >/dev/null || python_bin=python3
command -v "$python_bin" >/dev/null || { echo 'Python 3 is required for local setup.' >&2; exit 2; }

"$python_bin" -B - <<'PY'
import os
import re
import secrets
from pathlib import Path

path = Path('.env')
source = path.read_text(encoding='utf-8-sig') if path.exists() else Path('.env.example').read_text(encoding='utf-8-sig')
lines = source.splitlines()
for key in ('MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD'):
    matches = [i for i, line in enumerate(lines) if re.match(r'^\s*' + key + r'\s*=', line)]
    if matches and lines[matches[-1]].split('=', 1)[1].strip().strip('"\''):
        continue
    entry = key + '=' + secrets.token_urlsafe(32)
    if matches:
        lines[matches[-1]] = entry
    else:
        lines.append(entry)
if not path.exists() or source != '\n'.join(lines) + '\n':
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    if os.name != 'nt':
        path.chmod(0o600)
print('Environment file ready: .env')
PY

export DATABASE_SQL_DIR=./database
docker compose config --quiet
docker compose build
bash ./setup/database.sh
printf '\nSample data (optional): bash ./setup/database-data.sh\nAPI: http://localhost:%s/api/v1\n' "$(sed -n 's/^BACKEND_PORT=//p' .env | tail -1)"
printf 'Health: http://localhost:%s/health/ready\n' "$(sed -n 's/^BACKEND_PORT=//p' .env | tail -1)"
