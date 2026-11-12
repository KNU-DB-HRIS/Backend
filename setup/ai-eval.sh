#!/usr/bin/env bash
# NL2SQL 평가: L1~L3 질문을 simple·enhanced 두 방식으로 돌려 ai/eval/out/report.md 작성
#   bash ./setup/ai-eval.sh                # 기본 1회
#   bash ./setup/ai-eval.sh --repeat 3     # 반복
#   bash ./setup/ai-eval.sh --only L3      # 일부만
#   bash ./setup/ai-eval.sh --sleep 4      # 무료 티어 분당 한도 대비
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash가 /eval 경로를 바꾸지 않게

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT_DIR"
[[ -f .env ]] || { echo 'Missing .env. Run bash ./setup/setup.sh first.' >&2; exit 2; }
docker compose ps --status running --services | grep -Fxq ai || {
    echo 'AI service is not running. Run bash ./setup/ai.sh first.' >&2
    exit 2
}
mkdir -p ai/eval/out
docker compose run --rm --no-deps -T -v ./ai/eval:/eval backend python /eval/run_eval.py "$@"
