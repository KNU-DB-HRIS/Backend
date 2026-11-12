#!/usr/bin/env bash
# HR AI LLM 설정을 .env에 반영 (키 값은 출력하지 않음)
# - 배포 워크플로: GitHub secret LLM_API_KEY가 있으면 서버에서 자동 실행
# - 직접 실행: read -rs LLM_API_KEY && export LLM_API_KEY && bash ./setup/llm-env.sh && bash ./setup/ai.sh
# 기본값은 DeepSeek(생각 모드 끔, JSON 모드). 다른 제공자는 LLM_BASE_URL·LLM_MODEL·LLM_JSON_MODE·LLM_EXTRA_BODY를 같이 넘김
# AI_DATABASE_URL(읽기 전용 계정)이 비어 있으면 setup.sh와 같은 형식으로 만들고, 이미 있으면 그대로 둠
set -euo pipefail
umask 077

[[ $# -eq 0 ]] || { echo 'Usage: LLM_API_KEY=... bash ./setup/llm-env.sh' >&2; exit 2; }
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT_DIR"
[[ -f .env ]] || { echo 'Missing .env. Run bash ./setup/setup.sh first.' >&2; exit 2; }
[[ -n "${LLM_API_KEY:-}" ]] || { echo 'LLM_API_KEY is empty.' >&2; exit 2; }
[[ "$LLM_API_KEY" != *[[:space:]\'\"]* ]] || { echo 'LLM_API_KEY contains spaces or quotes. Check the copied value.' >&2; exit 2; }

if [[ -z "${LLM_BASE_URL:-}" ]]; then
    LLM_BASE_URL='https://api.deepseek.com'
    LLM_MODEL="${LLM_MODEL:-deepseek-flash}"
    LLM_JSON_MODE="${LLM_JSON_MODE:-1}"
    # 생각 모드 끔: 응답 1~2초, temperature 0 적용(같은 질문에 같은 SQL). 켜면 최대 12초 이상 걸려 시간 초과 위험
    [[ -n "${LLM_EXTRA_BODY:-}" ]] || LLM_EXTRA_BODY="'{\"thinking\":{\"type\":\"disabled\"}}'"
fi
[[ -n "${LLM_MODEL:-}" ]] || { echo 'LLM_MODEL is required when LLM_BASE_URL is set.' >&2; exit 2; }

upsert() {  # 같은 키가 여러 줄이면 첫 자리에 하나만 남김
    KEY="$1" VAL="$2" awk '
        BEGIN { k = ENVIRON["KEY"]; v = ENVIRON["VAL"]; done = 0 }
        $0 ~ "^[[:space:]]*" k "[[:space:]]*=" { if (!done) { print k "=" v; done = 1 } next }
        { print }
        END { if (!done) print k "=" v }
    ' .env > .env.llm-tmp
    if cmp -s .env .env.llm-tmp; then rm -f .env.llm-tmp; echo "  $1: unchanged"; else mv .env.llm-tmp .env; echo "  $1: updated"; fi
}

echo 'HR AI LLM settings (.env):'
upsert LLM_BASE_URL "$LLM_BASE_URL"
upsert LLM_MODEL "$LLM_MODEL"
upsert LLM_API_KEY "$LLM_API_KEY"
upsert LLM_JSON_MODE "${LLM_JSON_MODE:-0}"
upsert LLM_EXTRA_BODY "${LLM_EXTRA_BODY:-}"
echo "  (model=$LLM_MODEL, key length=${#LLM_API_KEY})"

if ! grep -Eq '^AI_DATABASE_URL=mysql\+pymysql://.+' .env; then
    db="$(sed -n 's/^MYSQL_DATABASE=//p' .env | tail -1)"
    password="$(od -An -tx1 -N24 /dev/urandom | tr -d ' \n')"
    upsert AI_DATABASE_URL "mysql+pymysql://hris_ai:${password}@mysql:3306/${db:-hris}?charset=utf8mb4"
fi
chmod 600 .env
