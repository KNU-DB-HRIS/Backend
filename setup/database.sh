#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 0 ]] || { echo 'Usage: bash database.sh' >&2; exit 2; }
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT_DIR"
[[ -f .env ]] || { echo 'Missing .env. Run bash setup.sh first.' >&2; exit 2; }
command -v docker >/dev/null || { echo 'Docker is required.' >&2; exit 2; }

docker compose config --quiet
docker compose up -d --wait --wait-timeout 180 mysql
docker compose run --rm --build -T migrate
docker compose up -d --wait --wait-timeout 300 backend

printf 'Database schema migrations completed.\n'