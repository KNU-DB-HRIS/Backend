# HRIS Backend

Flask + MySQL 8.4 기반 HRIS REST API입니다. 노션 **데이터베이스 프로그래밍 → Term Project → API 명세서**를 기준으로 `/api/v1` 엔드포인트를 제공합니다. 인증은 HttpOnly 쿠키 세션 및 CSRF, 데이터 저장은 MySQL, 애플리케이션 실행은 Gunicorn을 사용합니다.

## 프로젝트 구조

```text
Backend/
├── app/
│   ├── modules/             # 인증, 인사, 급여, 조직, 평가, 전자결재, 문서, AI 등
│   ├── cli.py               # DB 마이그레이션 및 계정 관리
│   ├── seed_demo.py         # 개발용 샘플 데이터 등록 로직
│   ├── config.py            # 환경 변수
│   ├── db.py                # DB 연결 및 트랜잭션
│   ├── security.py          # 인증, 권한, CSRF
│   └── ...
├── database/                # 번호 순서대로 적용되는 SQL 마이그레이션
├── ai/                      # HR AI(NL2SQL) FastAPI 서비스 · 평가 도구(ai/eval)
├── config/                  # Gunicorn 설정
├── requirements.txt         # 통합 Python 의존성
├── compose.yaml             # MySQL, 마이그레이션, API 서비스
├── Dockerfile
├── .env.example
├── setup/
│   ├── setup.sh             # 최초 설정 및 서버 실행
│   ├── database.sh          # DB 스키마 마이그레이션만 수행
│   └── database-data.sh     # 개발용 샘플 데이터 일괄 등록
└── wsgi.py
```

## 설치 및 실행

Docker Desktop(Compose v2), Python 3, Bash가 필요합니다. Windows에서는 Git Bash를 권장합니다.

```bash
cd Backend

chmod +x ./setup/setup.sh
chmod +x ./setup/database.sh
chmod +x ./setup/database-data.sh

bash ./setup/setup.sh
bash ./setup/database-data.sh
```

스크립트는 `setup/`에 보관하지만 **실행할 때는 자동으로 프로젝트 루트(`backend/`)로 이동**합니다. 명령어는 Git Bash에서 프로젝트 루트 기준으로 실행하면 됩니다. `.env`가 없을 경우 `setup.sh`가 루트의 `.env.example`을 복사하고 DB 비밀번호를 생성합니다. 기존 `.env`를 사용한다면 실행 전에 루트에 보관하세요.

- `setup.sh`: `.env` 생성(처음에는 DB 비밀번호 무작위 생성), Docker 이미지 빌드, 스키마 적용, 서버 기동
- `database.sh`: DB 스키마 마이그레이션만 실행. 회사, 직원, 관리자, 테스트 데이터를 등록하지 않음
- `database-data.sh`: **선택적으로** 실행. 빈 개발용 DB에 회사·부서·직원 10명과 화면용 데이터를 일괄 등록. 사용자 입력 프롬프트 없음

서버 시작 후 API는 `http://localhost:8080/api/v1`, 상태 확인은 `http://localhost:8080/health/ready`입니다. `.env`에서 `BACKEND_PORT`를 변경할 수 있습니다.

### 샘플 데이터

샘플 회사는 `샘플테크`(가상 사업자번호 `999-99-99999`)이며, 5개 부서(인사·개발·디자인·영업·경영지원)를 구성합니다.

| 로그인 ID | 직원명 | 부서 | 권한 |
| --- | --- | --- | --- |
| admin01 | 김서연 | 인사팀 | HR_ADMIN |
| employee02 | 이도윤 | 개발팀 | EMPLOYEE |
| employee03 | 박하린 | 개발팀 | EMPLOYEE |
| employee04 | 정민준 | 디자인팀 | EMPLOYEE |
| employee05 | 최유진 | 영업팀 | EMPLOYEE |
| employee06 | 윤지호 | 경영지원팀 | EMPLOYEE |
| employee07 | 한수빈 | 인사팀 | EMPLOYEE |
| employee08 | 오서준 | 개발팀 | EMPLOYEE |
| employee09 | 김나연 | 영업팀 | EMPLOYEE |
| employee10 | 송지우 | 경영지원팀 | EMPLOYEE |

급여 구성과 변경 이력, 지난달 급여명세서, 이번 달 근태, 평가 회차·진행률, 전자결재 4건, 예정된 인사 일정 3건도 함께 생성합니다. 금액, 세금, 주소, 사업자번호, 연락처 등은 모두 **시연 전용 가상 데이터**이며 실제 계산·제출용으로 사용하면 안 됩니다.

샘플 계정마다 무작위 비밀번호를 발급해 루트의 `.seed-credentials.csv` 파일에 저장합니다. 실행 후 Git Bash에서 확인할 수 있습니다.

```bash
cat ./.seed-credentials.csv
```

이 파일은 Git 및 Docker 빌드에서 제외되며 생성 시 파일 권한을 제한합니다. **삭제하거나 외부에 공유하지 마세요.** 샘플 데이터 재실행 시 계정 비밀번호는 변경하지 않으므로 처음 생성된 파일을 보관해야 합니다.

개발 DB에 이미 회사 또는 직원 데이터가 존재하면 샘플 등록을 거부합니다. 이미 정상 등록된 샘플 데이터에서 스크립트를 재실행하면 중복 생성하지 않습니다. 초기 데이터는 한 트랜잭션으로 등록하므로 오류 발생 시 해당 실행의 데이터 변경은 롤백됩니다. `APP_ENV=production` 환경에서는 샘플 데이터 등록을 차단합니다.

## 운영 명령

```bash
bash ./setup/database.sh                    # 새 SQL 마이그레이션 적용
bash ./setup/database-data.sh               # 개발용 샘플 데이터 등록

docker compose ps                   # 컨테이너 상태
docker compose logs -f backend      # API 로그
docker compose restart backend      # API 재시작
docker compose down                 # 컨테이너 중지 (DB 볼륨 유지)
docker compose up -d                # 재기동
```

일반 계정은 필요할 때 별도로 생성할 수 있습니다. 아래 명령은 비밀번호를 대화형으로 입력받습니다.

```bash
docker compose exec backend flask --app wsgi:app create-user --employee-id 2 --username newuser
```

### API 인증 예시

```bash
DOMAIN=localhost:8080
curl -i -c cookies.txt -H 'Content-Type: application/json' \
  -d '{"username":"admin01","password":"CSV에서_확인한_비밀번호"}' \
  "http://$DOMAIN/api/v1/auth/login"

curl -i -b cookies.txt "http://$DOMAIN/api/v1/auth/me"
```

로그인 응답의 `csrf_token`을 확인한 다음, `POST`, `PATCH`, `DELETE` 요청에 `X-CSRF-Token` 헤더로 전달합니다. 프론트엔드에서는 `credentials: 'include'`를 설정해야 하며, `.env`의 `CORS_ORIGINS`에는 해당 프론트엔드 Origin을 등록해야 합니다.

## HR AI (NL2SQL)

브라우저는 Flask의 `POST /api/v1/ai/queries`만 호출합니다(HR_ADMIN 전용). Flask가 `ai` 서비스(FastAPI, `ai/`)에 질문과 허용 스키마를 보내 SQL을 받고, `app/modules/ai/sql_policy.py`로 검증·회사 범위 주입을 한 뒤 **읽기 전용 계정 `hris_ai`**로 실행합니다. AI 서비스는 DB에 접속하지 않고, LLM API 키는 `ai` 컨테이너에만 들어갑니다.

```text
브라우저 → Flask /api/v1/ai/queries → ai:8000 /queries (LLM 호출, SQL 생성·사전 점검)
        ← 결과 표·답변·실행 SQL ← Flask: sql_policy 검증 → hris_ai 계정으로 SELECT 실행
```

### 설정

1. `.env`에 LLM을 설정합니다. OpenAI 호환 `/chat/completions`면 어느 제공자든 됩니다. 키는 Git에 올리지 마세요.

   ```dotenv
   LLM_BASE_URL=https://api.deepseek.com
   LLM_MODEL=deepseek-flash
   LLM_API_KEY=발급받은_키
   LLM_JSON_MODE=1
   LLM_EXTRA_BODY='{"thinking":{"type":"disabled"}}'
   ```

   DeepSeek는 생각 모드가 기본으로 켜져 있어 응답이 느리고(Flask 20초 제한) temperature가 무시되므로 `LLM_EXTRA_BODY`로 끕니다. 다른 제공자 예시는 `.env.example`에 있습니다.

2. `bash ./setup/setup.sh`를 실행합니다. `AI_DATABASE_URL`이 비어 있으면 읽기 전용 계정 비밀번호를 만들어 채우고, 마지막에 `setup/ai.sh`가 계정 생성·권한 부여·AI 서비스 기동을 합니다. 이미 설치된 환경에서는 `bash ./setup/ai.sh`만 실행해도 됩니다(여러 번 실행해도 안전).
3. 상태 확인: `http://localhost:8001/health`의 `llm_configured`가 `true`인지 확인합니다.

`hris_ai` 계정은 `SAFE_TABLES`에 적힌 열에만 열 단위 `SELECT` 권한을 받습니다. 검증기를 우회하는 SQL이 와도 급여·연락처·계정 정보는 DB 권한 단계에서 거부됩니다. `SAFE_TABLES`를 바꾸면 `bash ./setup/ai.sh`를 다시 실행해 권한을 맞추세요.

### 평가 (과제 NL2SQL 확장)

```bash
bash ./setup/database-data.sh           # 샘플 데이터 필요
bash ./setup/ai-eval.sh --repeat 3      # L1~L3 질문 × simple·enhanced 프롬프트 × 3회
```

- 질문·정답 SQL: `ai/eval/questions.json` (L1 단순 조건, L2 JOIN·집계·서브쿼리, L3 업무 용어·모호성)
- simple = 테이블·열 이름만, enhanced = PK·FK·관계·열 의미·코드값·업무 용어·집계 기준·예시 추가
- 생성 SQL과 정답 SQL을 같은 검증기·읽기 전용 계정으로 실행해 결과 집합을 비교하고, `ai/eval/out/report.md`에 수준별 정답률·오류 유형·오답 SQL을 기록합니다.
- 업무 용어 정의(장기근속 3년, 신입 1년 미만 등)는 `ai/nl2sql/prompts.py`의 `GLOSSARY`에 있으며 팀 합의 전 제안값입니다.

### 테스트

```bash
cd ai && python -m pytest -q    # fastapi·httpx·pytest·sqlglot 필요, Flask 쪽 계약 테스트는 requirements.txt 설치 시 함께 실행
```

## 운영 주의 사항

- `database/`의 기존 SQL은 수정하지 말고 새 번호로 마이그레이션 파일을 추가합니다. 적용 이력은 `schema_migrations`에서 관리합니다.
- `.env`, `.seed-credentials.csv`는 Git에 올리지 않습니다. 운영 DB에서 시드 스크립트를 실행하지 않습니다.
- MySQL 볼륨과 발급 문서 볼륨을 정기적으로 백업해야 합니다. `docker compose down -v`는 볼륨의 실제 데이터를 삭제하므로 주의하세요.
- 기본 API 포트는 로컬 인터페이스에만 바인딩합니다. 배포 시 HTTPS 리버스 프록시, 비밀정보 관리 및 실제 도메인에 맞춘 CORS 설정이 필요합니다.
- HR AI 기능은 `.env`에 LLM 설정이 있어야 작동합니다(위 "HR AI" 참고). LLM 설정이 없어도 다른 API는 정상 동작하며 AI 요청만 오류를 돌려줍니다. 노션에서 보류한 `SAL-04`, `EVAL-04` API는 구현되지 않았습니다.