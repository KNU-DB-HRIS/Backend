
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

test -f .env
docker compose config --quiet

if ! docker compose up -d --wait --wait-timeout 360 mysql; then
  echo "ERROR: MySQL initialization failed."
  docker compose ps mysql
  docker compose logs --tail=100 mysql
  docker inspect \
    --format '{{range .State.Health.Log}}{{println .ExitCode .Output}}{{end}}' \
    "$(docker compose ps -q mysql)" || true
  exit 1
fi

docker compose run --rm --build -T migrate
docker compose up -d --wait --wait-timeout 300 backend

echo "Database schema migrations completed."
