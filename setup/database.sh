#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 0 ]] || { echo 'Usage: bash database.sh' >&2; exit 2; }
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT_DIR"
[[ -f .env ]] || { echo 'Missing .env. Run bash setup.sh first.' >&2; exit 2; }
command -v docker >/dev/null || { echo 'Docker is required.' >&2; exit 2; }


if ! docker compose up -d --wait --wait-timeout 360 mysql; then
  echo "ERROR: MySQL initialization failed."
  docker compose ps mysql
  docker compose logs --tail=100 mysql
  docker inspect \
    --format '{{range .State.Health.Log}}{{println .ExitCode .Output}}{{end}}' \
    "$(docker compose ps -q mysql)" || true
  exit 1
fi


printf 'Database schema migrations completed.\n'