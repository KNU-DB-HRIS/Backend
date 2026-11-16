# HRIS Backend

Flask와 MySQL 8.4 기반 HRIS REST API입니다. 노션 **데이터베이스 프로그래밍 → Term Project → API 명세서**를 기준으로 `/api/v1` 엔드포인트를 제공합니다. 인증은 HttpOnly 쿠키 세션과 CSRF 토큰, 데이터 저장은 MySQL, 애플리케이션 실행은 Gunicorn을 사용하며, 자연어 질문을 SQL로 바꿔 조회하는 HR AI(NL2SQL) 서비스가 함께 들어 있습니다.

MySQL, API 서버, HR AI 서버가 모두 Docker 컨테이너로 실행되므로 내 컴퓨터에 MySQL이나 Python 패키지를 따로 설치할 필요가 없습니다. 아래 1번부터 순서대로 따라 하면 Docker 설치부터 API 호출까지 마칠 수 있습니다. 처음 한 번만 하면 되는 단계는 1번부터 4번까지이고, 이후에는 7번의 명령으로 켜고 끕니다.

## 1. 준비물

| 항목 | 용도 | 비고 |
| --- | --- | --- |
| Docker Desktop(Windows, macOS) 또는 Docker Engine(Linux) | MySQL, API, HR AI 컨테이너 실행 | Docker Compose **v2.17 이상** |
| Git | 저장소 받기 | Windows는 Git for Windows를 설치하고 모든 명령을 **Git Bash**에서 실행 |
| Python 3.9 이상 | 설치 스크립트가 `.env`와 샘플 계정 파일을 만들 때 사용 | 표준 라이브러리만 쓰므로 별도 패키지 설치는 필요 없음 |
| DeepSeek API 키 | HR AI 기능 | 팀장(임창학)의 키를 함께 사용하므로 직접 발급하지 않음. 키가 없어도 HR AI만 꺼지고 나머지 API는 정상 동작 |

Docker Desktop은 메모리 8GB 이상인 컴퓨터를 권장합니다. 이미지와 DB를 합쳐 디스크 여유 공간이 3GB 정도 필요합니다.

## 2. Docker, Git, Python 설치

내 운영체제의 항목만 따라 하면 됩니다. 이미 설치된 프로그램은 건너뛰고, 마지막에 2-4의 설치 확인을 합니다.

### 2-1. Windows

**Docker**

Docker Desktop은 WSL 2 위에서 동작합니다. 64비트 Windows 10 22H2 이상 또는 Windows 11이 필요하고, BIOS(UEFI)에서 가상화가 켜져 있어야 합니다.

1. **관리자 권한 PowerShell**에서 WSL을 설치하거나 최신으로 올린 뒤, 안내가 나오면 재부팅합니다.

   ```powershell
   wsl --install
   wsl --update
   ```

2. [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)를 내려받아 설치합니다. WSL 2 사용 여부를 묻는 항목이 나오면 켠 상태로 둡니다.
3. 시작 메뉴에서 Docker Desktop을 실행하고 약관에 동의합니다. 창 왼쪽 아래 상태가 'Engine running'이 될 때까지 기다립니다.

**Git**

4. [Git for Windows 다운로드 페이지](https://git-scm.com/install/windows)에서 x64 Setup을 받아 설치합니다(ARM 노트북은 ARM64 Setup). 설치 화면의 선택지는 모두 기본값 그대로 두고 Next를 눌러도 됩니다. winget을 쓴다면 PowerShell에서 아래 명령으로도 설치할 수 있습니다.

   ```powershell
   winget install --id Git.Git -e --source winget
   ```

5. 설치가 끝나면 시작 메뉴에서 **Git Bash**를 엽니다. 이후 README의 명령은 모두 Git Bash에서 실행합니다.

**Python 3**

6. [Python Windows 다운로드 페이지](https://www.python.org/downloads/windows/)에서 최신 안정 버전의 **Windows installer (64-bit)**를 받아 실행합니다(ARM 노트북은 ARM64).
7. 설치 첫 화면 아래쪽의 **'Add python.exe to PATH'를 반드시 체크**한 뒤 Install Now를 누릅니다. 이 체크를 빠뜨리면 Git Bash에서 `python` 명령을 찾지 못합니다.
8. Windows 설정 → 앱 → 고급 앱 설정 → **앱 실행 별칭**에서 '앱 설치 관리자'의 `python.exe`, `python3.exe` 두 항목을 끕니다. 켜져 있으면 `python`을 실행할 때 진짜 Python 대신 Microsoft Store가 열립니다.
9. 열려 있던 Git Bash를 모두 닫고 새로 엽니다(새 PATH는 새 창부터 적용됩니다).

> python.org는 Windows용으로 'Python install manager'도 제공하며, 위의 설치 파일(Windows installer)은 Python 3.16부터 나오지 않을 예정입니다. install manager로 설치했다면 처음 실행할 때 명령 폴더를 PATH에 추가할지 묻는 질문에 yes를 고르고, 앱 실행 별칭의 'Python (default)' 항목은 켜 둔 채로 두세요.

### 2-2. macOS

**Docker**

1. [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/)에서 내 컴퓨터 칩(Apple Silicon 또는 Intel)에 맞는 파일을 받아 설치합니다. 칩은 Apple 메뉴 → 이 Mac에 관하여에서 확인할 수 있습니다.
2. 응용 프로그램 폴더에서 Docker를 실행하고, 메뉴 막대의 고래 아이콘이 실행 중 상태가 될 때까지 기다립니다.

**Git과 Python 3**

macOS는 Apple의 Command Line Tools 하나로 Git과 Python 3가 함께 설치됩니다.

3. 터미널(응용 프로그램 → 유틸리티 → 터미널)에서 아래 명령을 실행합니다. 설치 안내 창이 뜨면 '설치'를 누르고, 이미 설치되어 있다는 메시지가 나오면 그대로 넘어가면 됩니다.

   ```bash
   xcode-select --install
   ```

4. 설치가 끝나면 `git --version`, `python3 --version`으로 확인합니다. Command Line Tools의 Python(3.9)으로도 설치 스크립트가 정상 동작합니다.

Homebrew를 쓰고 있다면 `brew install git python`으로 최신 버전을 설치해도 됩니다.

### 2-3. Linux(Ubuntu)

배포 서버와 같은 환경입니다. Docker의 자세한 설치 방법은 [Docker Engine 설치 문서](https://docs.docker.com/engine/install/ubuntu/)를 따르고, 개발용으로는 공식 설치 스크립트를 써도 됩니다.

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

마지막 줄은 `sudo` 없이 `docker`를 쓰기 위한 설정이며, 로그아웃 후 다시 로그인해야 적용됩니다.

Git과 Python 3는 apt로 설치합니다. Ubuntu에는 Python 3가 기본으로 들어 있는 경우가 많고, 이미 설치되어 있으면 최신 상태라는 메시지만 나옵니다.

```bash
sudo apt update
sudo apt install -y git python3
```

### 2-4. 설치 확인

Docker를 실행해 둔 상태에서 **새 터미널 창**을 열어 아래 명령을 실행합니다(Windows는 Git Bash). `docker compose version`이 v2.17.0 이상이고, `hello-world`에서 'Hello from Docker!'가 나오고, Git 버전과 Python 3.9 이상의 버전이 출력되면 준비가 끝난 것입니다.

```bash
docker version
docker compose version
docker run --rm hello-world
git --version
python3 --version || python --version
```

## 3. 저장소 받기와 환경 파일

```bash
git clone https://github.com/KNU-DB-HRIS/Backend.git
cd Backend
cp .env.example .env
```

`.env`는 내 컴퓨터 전용 설정 파일이며 Git에 올라가지 않습니다. 대부분은 그대로 두면 되고, 필요할 때 아래 항목만 바꿉니다.

| 항목 | 기본값 | 설명 |
| --- | --- | --- |
| `BACKEND_PORT` | `8080` | API 서버 포트. 다른 프로그램이 8080을 쓰고 있으면 `18080` 등으로 변경 |
| `AI_PORT` | `8001` | HR AI 서버 포트(내 컴퓨터에서만 접속 가능) |
| `CORS_ORIGINS` | `http://localhost:5173,...` | 브라우저에서 API를 직접 호출하는 프론트엔드 주소 |
| `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` | 비어 있음 | 비워 두면 4단계에서 무작위로 생성 |
| `AI_DATABASE_URL` | 비어 있음 | HR AI 읽기 전용 DB 계정. 비워 두면 자동 생성 |
| `LLM_*` | 비어 있음 | HR AI용 LLM 설정. 아래 방법으로 입력 |

## 4. HR AI 키 넣기

HR AI는 팀장(임창학)의 DeepSeek API 키 하나를 팀이 함께 사용합니다. **API 키는 프로젝트 단체방에 있습니다.** 현재 DeepSeek API 키에는 $2를 충전하였으며, 프로젝트 종료 후 삭제할 예정입니다. 

아래 명령을 한 줄 그대로 실행하고, `DeepSeek API key:`가 나오면 키를 붙여 넣은 뒤 Enter를 누르세요. 입력한 키는 화면과 셸 기록에 남지 않고, 모델 이름과 응답 옵션(DeepSeek 생각 모드 끔, JSON 모드)도 함께 설정됩니다. macOS 기본 셸(zsh)에서도 동작하도록 `bash -c`로 감쌌습니다.

```bash
bash -c 'read -rsp "DeepSeek API key: " LLM_API_KEY; echo; export LLM_API_KEY; bash ./setup/llm-env.sh'
```

키를 붙여 넣어도 화면에는 아무것도 보이지 않는 것이 정상입니다. Git Bash에서는 Ctrl+V 대신 **Shift+Insert** 또는 마우스 오른쪽 클릭으로 붙여 넣습니다. `LLM_API_KEY: updated`와 `key length=35` 같은 출력이 나오면 들어간 것입니다.

**이미 4단계(`setup.sh`)까지 마친 뒤에 키를 넣었다면** 이어서 아래 명령으로 HR AI만 다시 적용하고, http://localhost:8001/health 에서 `"llm_configured":true`가 나오는지 확인합니다. 키를 넣지 않은 상태에서는 HR AI 화면에 'AI 서버에 연결하지 못했습니다'가 뜹니다.

```bash
bash ./setup/ai.sh
```

직접 편집하고 싶다면 `.env`를 VS Code 같은 코드 편집기로 열어 아래 다섯 줄을 채워도 됩니다. macOS 텍스트 편집기(TextEdit)는 따옴표를 둥근 따옴표로 바꿔 마지막 줄이 깨지므로 쓰지 마세요.

```dotenv
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=발급받은_키
LLM_JSON_MODE=1
LLM_EXTRA_BODY='{"thinking":{"type":"disabled"}}'
```

잔액을 팀이 함께 쓰므로 평가(`ai-eval.sh`)처럼 호출이 많은 작업은 팀장과 상의한 뒤 실행해 주세요. 다른 LLM 제공자(Gemini, OpenAI, Ollama) 예시는 `.env.example`의 주석에 있습니다.

## 5. 설치와 실행

```bash
bash ./setup/setup.sh
```

스크립트는 어느 위치에서 실행해도 프로젝트 루트로 이동해 아래 순서로 진행합니다. 처음에는 이미지를 받고 빌드하느라 3~5분 정도 걸립니다.

1. `.env`에 비어 있는 DB 비밀번호와 HR AI 읽기 전용 계정 주소를 무작위로 채웁니다. 이미 값이 있으면 그대로 둡니다.
2. API 서버와 HR AI 서버 이미지를 빌드합니다.
3. MySQL을 띄우고 `database/`의 SQL 마이그레이션을 번호 순서대로 적용합니다.
4. API 서버를 띄우고 정상 응답할 때까지 기다립니다.
5. HR AI 읽기 전용 계정(`hris_ai`)과 권한을 만들고 HR AI 서버를 띄웁니다.

마지막에 `HR AI ready. Read-only account applied.`가 나오면 설치가 끝난 것입니다. LLM 키를 넣지 않았다면 `LLM is not configured yet` 안내가 함께 나오는데, HR AI만 꺼진 상태이므로 그대로 진행해도 됩니다.

화면 확인용 샘플 데이터가 필요하면 이어서 실행합니다(선택, 1분 이내).

```bash
bash ./setup/database-data.sh
cat ./.seed-credentials.csv
```

`.seed-credentials.csv`에 샘플 계정의 아이디와 비밀번호가 저장됩니다. 비밀번호는 설치할 때마다 무작위로 만들어지며, 자세한 내용은 아래 '샘플 데이터'를 참고하세요.

## 6. 실행 확인

```bash
docker compose ps
```

`mysql`, `backend`, `ai` 세 서비스가 모두 `(healthy)`이면 정상입니다. 포트를 바꿨다면 아래 주소의 8080, 8001도 바꿔서 확인합니다.

| 주소 | 정상 결과 |
| --- | --- |
| http://localhost:8080/health/ready | `{"status":"ok"}` |
| http://localhost:8001/health | `"llm_configured":true` 포함(HR AI 키를 넣은 경우) |

API 주소는 `http://localhost:8080/api/v1/...`입니다(`/api/v1` 자체는 404가 정상). 로그인과 HR AI 호출은 '샘플 데이터'를 등록한 뒤 아래 'API 인증 예시'로 확인할 수 있습니다.

## 7. 프론트엔드 연결

화면은 [KNU-DB-HRIS/Frontend](https://github.com/KNU-DB-HRIS/Frontend) 저장소에 있습니다(Node.js 20 이상 필요). 백엔드를 켜 둔 상태에서 실행합니다.

```bash
git clone https://github.com/KNU-DB-HRIS/Frontend.git
cd Frontend
npm ci
cp .env.example .env
npm run dev
```

프론트엔드 저장소는 비공개라서 처음 받을 때 GitHub 로그인을 요구합니다. GitHub는 git에서 계정 비밀번호를 받지 않으므로, 비밀번호를 물으면 아래 방법으로 로그인하세요.

| 환경 | 방법 |
| --- | --- |
| Windows(Git for Windows) | 브라우저 로그인 창이 뜨면 GitHub 계정으로 로그인. 한 번 하면 저장됨 |
| macOS, Linux | [GitHub CLI](https://cli.github.com/)를 설치하고(macOS는 `brew install gh`) `gh auth login`으로 로그인한 뒤 `gh auth setup-git`을 한 번 실행 |
| 공통(대안) | Username에 GitHub 아이디, Password에 비밀번호 대신 [Personal Access Token](https://github.com/settings/tokens) 입력 |

KNU-DB-HRIS 조직 멤버가 아니면 로그인해도 접근이 거부되므로 팀장에게 초대를 요청하세요.

터미널에 나온 `Local:` 주소(보통 http://localhost:5173)로 접속해 `admin01`로 로그인합니다. 백엔드 포트를 바꿨다면 프론트엔드 `.env`의 `VITE_BACKEND_ORIGIN`도 같은 포트로 바꾸고 `npm run dev`를 다시 실행합니다. 개발 서버가 API 요청을 백엔드로 전달하므로 이 경우에는 `CORS_ORIGINS`를 바꾸지 않아도 됩니다.

## 8. 끄기, 다시 켜기, 초기화

| 명령 | 설명 |
| --- | --- |
| `docker compose ps` | 컨테이너 상태 |
| `docker compose logs -f backend` | API 로그 (`ai`, `mysql`도 같은 방식, Ctrl+C로 빠져나옴) |
| `docker compose restart backend` | API 재시작 |
| `docker compose down` | 끄기 (DB 데이터는 유지) |
| `docker compose up -d` | 다시 켜기 |
| `git pull` 후 `bash ./setup/setup.sh` | 최신 코드 반영. 빌드, 새 마이그레이션, HR AI 권한까지 다시 적용하고 `.env` 값은 유지 |
| `bash ./setup/database.sh` | 새 SQL 마이그레이션만 적용 |
| `bash ./setup/ai.sh` | LLM 설정이나 `SAFE_TABLES`를 바꾼 뒤 HR AI만 다시 적용 |
| `docker compose down -v` | **주의.** DB와 발급 문서까지 모두 삭제. 처음부터 다시 설치할 때만 사용 |

Docker Desktop을 종료하면 컨테이너도 함께 멈추고, 다시 켜면 자동으로 올라옵니다.

일반 계정은 필요할 때 별도로 만들 수 있습니다. 아래 명령은 비밀번호를 대화형으로 입력받습니다.

```bash
docker compose exec backend flask --app wsgi:app create-user --employee-id 2 --username newuser
```

## 샘플 데이터

샘플 회사는 `샘플테크`(가상 사업자번호 `999-99-99999`)이며, 5개 부서(인사, 개발, 디자인, 영업, 경영지원)로 구성합니다.

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

급여 구성과 변경 이력, 지난달 급여명세서, 이번 달 근태, 평가 회차와 진행률, 전자결재 4건, 예정된 인사 일정 3건도 함께 생성합니다. 금액, 세금, 주소, 사업자번호, 연락처 등은 모두 **시연 전용 가상 데이터**이며 실제 계산이나 제출에 사용하면 안 됩니다.

샘플 계정마다 무작위 비밀번호를 발급해 루트의 `.seed-credentials.csv` 파일에 저장합니다. 이 파일은 Git과 Docker 빌드에서 제외되며 생성 시 파일 권한을 제한합니다. **삭제하거나 외부에 공유하지 마세요.** 샘플 데이터를 다시 등록해도 계정 비밀번호는 바뀌지 않으므로 처음 생성된 파일을 보관해야 합니다.

DB에 이미 회사나 직원 데이터가 있으면 샘플 등록을 거부하고, 이미 정상 등록된 샘플 데이터에서 다시 실행하면 중복 생성하지 않습니다. 초기 데이터는 한 트랜잭션으로 등록하므로 오류가 나면 그 실행의 변경은 모두 롤백됩니다. `APP_ENV=production` 환경에서는 샘플 데이터 등록을 차단합니다.

## API 인증 예시

로그인(`POST /auth/login`)과 내 정보 조회(`GET /auth/me`) 응답에 `csrf_token`이 들어 있고, `POST`, `PATCH`, `DELETE` 요청에는 이 값을 `X-CSRF-Token` 헤더로 보내야 합니다. **`/auth/me`를 호출할 때마다 토큰이 새로 발급되고 이전 토큰은 무효가 되므로**, 항상 가장 최근에 받은 토큰을 사용하세요. 아래 예시는 샘플 데이터의 관리자 계정으로 로그인하고, 내 정보를 조회하면서 받은 토큰으로 HR AI에 질문합니다.

```bash
API=http://localhost:8080/api/v1
PASSWORD=$(grep '^admin01,' .seed-credentials.csv | cut -d, -f2)

curl -s -c cookies.txt -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin01\",\"password\":\"$PASSWORD\"}" "$API/auth/login"; echo

ME=$(curl -s -b cookies.txt "$API/auth/me"); printf '%s\n' "$ME"
CSRF=$(printf '%s' "$ME" | sed -n 's/.*"csrf_token": *"\([^"]*\)".*/\1/p')

curl -s -b cookies.txt -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{"question":"부서별 재직 인원 알려줘"}' "$API/ai/queries"; echo
```

로그인 세션이 담긴 `cookies.txt`는 `.gitignore`에 들어 있어 커밋되지 않지만, 다 쓴 뒤에는 지워도 됩니다.

프론트엔드에서 API를 직접 호출할 때는 `credentials: 'include'`를 설정하고, `.env`의 `CORS_ORIGINS`에 해당 프론트엔드 주소를 등록해야 합니다.

## HR AI(NL2SQL)

브라우저는 Flask의 `POST /api/v1/ai/queries`만 호출합니다(HR_ADMIN 전용). Flask가 `ai` 서비스(FastAPI, `ai/`)에 질문과 허용 스키마를 보내 SQL을 받고, `app/modules/ai/sql_policy.py`로 검증하고 회사 범위를 주입한 뒤 **읽기 전용 계정 `hris_ai`**로 실행합니다. AI 서비스는 DB에 접속하지 않고, LLM API 키는 `ai` 컨테이너에만 들어갑니다.

```text
브라우저 → Flask /api/v1/ai/queries → ai:8000 /queries (LLM 호출, SQL 생성과 사전 점검)
        ← 결과 표, 답변, 실행 SQL ← Flask: sql_policy 검증 → hris_ai 계정으로 SELECT 실행
```

설정 방법은 3단계의 'HR AI 키 넣기'를 참고하세요. 이미 설치한 뒤 키를 넣었다면 `bash ./setup/ai.sh`만 실행하면 되고, 여러 번 실행해도 안전합니다. DeepSeek는 생각 모드가 기본으로 켜져 있어 응답이 느리고(Flask 20초 제한) temperature가 무시되므로 `LLM_EXTRA_BODY`로 끕니다.

`hris_ai` 계정은 `SAFE_TABLES`에 적힌 열에만 열 단위 `SELECT` 권한을 받습니다. 검증기를 우회하는 SQL이 와도 급여, 연락처, 계정 정보는 DB 권한 단계에서 거부됩니다. `SAFE_TABLES`를 바꾸면 `bash ./setup/ai.sh`를 다시 실행해 권한을 맞추세요.

### 평가(과제 NL2SQL 확장)

샘플 데이터(`database-data.sh`)를 등록한 상태에서 실행합니다. L1~L3 질문 19개를 simple, enhanced 두 프롬프트로 3회씩 돌리며 약 3분, LLM 비용은 100원 안팎이 듭니다. 팀 공용 키의 잔액을 쓰므로 실행 전에 팀장과 상의해 주세요.

```bash
bash ./setup/ai-eval.sh --repeat 3
```

질문과 정답 SQL은 `ai/eval/questions.json`(L1 단순 조건, L2 JOIN과 집계와 서브쿼리, L3 업무 용어와 모호성)에 있습니다. simple은 테이블과 열 이름만, enhanced는 PK, FK, 관계, 열 의미, 코드값, 업무 용어, 집계 기준, 예시를 추가로 줍니다. 생성 SQL과 정답 SQL을 같은 검증기와 읽기 전용 계정으로 실행해 결과 집합을 비교하고, `ai/eval/out/report.md`에 수준별 정답률, 오류 유형, 오답 SQL을 기록합니다. 업무 용어 정의(장기근속 3년, 신입 1년 미만 등)는 `ai/nl2sql/prompts.py`의 `GLOSSARY`에 있으며 팀 합의 전 제안값입니다.

### 테스트

`fastapi`, `httpx`, `pytest`, `sqlglot`이 설치된 Python 환경에서 실행합니다. Flask 쪽 계약 테스트는 `requirements.txt`까지 설치하면 함께 실행됩니다.

```bash
cd ai && python -m pytest -q
```

## 서버 배포

`main` 브랜치에 병합되면 GitHub Actions(`.github/workflows/deploy.yaml`)가 Oracle Cloud 서버(`/home/ubuntu/Backend`)에 자동으로 배포합니다. **`main`에 직접 push하지 말고 브랜치를 만들어 Pull Request로 병합하세요.**

배포는 `app/`, `ai/`, `setup/`, `wsgi.py`가 바뀐 경우에만 자동으로 실행됩니다. `compose.yaml`, `Dockerfile`, `requirements.txt`, `database/`만 바꾼 경우에는 저장소의 Actions → Deploy Backend → Run workflow로 직접 실행해야 서버에 반영됩니다.

서버에서는 아래 순서로 진행됩니다.

1. `git reset --hard origin/main`으로 서버 코드를 `main`과 똑같이 맞춥니다(서버에서 직접 고친 내용은 사라집니다).
2. 저장소 Secret `LLM_API_KEY`가 있으면 `setup/llm-env.sh`로 서버 `.env`에 HR AI 설정을 반영합니다.
3. 이미지를 빌드하고 컨테이너를 띄운 뒤 `setup/database.sh`(마이그레이션)와 `setup/ai.sh`(HR AI 권한)를 실행합니다.
4. 마지막 줄에 `HR AI health`를 출력합니다. `"llm_configured":true`면 HR AI까지 정상입니다.

서버 접속 정보(`ORACLE_CLOUD_VM_*`)와 팀장의 DeepSeek 키(`LLM_API_KEY`)는 저장소 Settings → Secrets and variables → Actions에 등록되어 있습니다. 키를 바꿀 때는 이 Secret만 바꾸고 Run workflow를 실행하면 됩니다. 서버 메모리가 1GB라서 배포 직후 2~3분 동안은 응답이 느릴 수 있습니다. 이 저장소는 공개 저장소이므로 Actions 로그도 누구나 볼 수 있습니다. 배포 스크립트에서 `.env` 내용이나 사용자 데이터를 출력하지 마세요.

## 문제 해결

| 증상 | 원인과 해결 |
| --- | --- |
| `Start Docker Desktop or Docker Engine first.` | Docker가 꺼져 있음. Docker Desktop을 실행하고 'Engine running'이 된 뒤 다시 실행 |
| `unknown flag: --wait-timeout` | Docker Compose가 오래됨. Docker Desktop을 최신으로 업데이트(v2.17 이상) |
| `permission denied ... docker.sock` (Linux) | `sudo usermod -aG docker $USER` 후 다시 로그인 |
| `Python was not found` 또는 Microsoft Store가 열림 (Windows) | Microsoft Store 바로가기가 실행된 것. 2-1의 7, 8번처럼 'Add python.exe to PATH'를 체크해 설치하고 앱 실행 별칭의 python 항목을 끈 뒤 Git Bash를 새로 열기 |
| `python: command not found` | Python이 없거나 PATH에 없음. 2장의 내 운영체제 항목대로 설치한 뒤 터미널을 새로 열기 |
| `set: pipefail\r: invalid option name` 또는 `$'\r': command not found` | Windows 줄바꿈(CRLF)으로 받은 예전 폴더. `git pull` 후 `git rm --cached -r . && git reset --hard`를 실행하거나 저장소를 새로 받기 |
| `port is already allocated` | 그 포트를 다른 프로그램이 사용 중. 예전에 zip이나 다른 폴더로 받아 둔 백엔드가 Docker를 켤 때 자동으로 같이 켜져 8080을 차지하는 경우가 많음. `docker ps`로 확인하고, 필요 없으면 그 폴더에서 `docker compose down`(DB 데이터는 유지) 후 `setup.sh` 다시 실행. 둘 다 쓰려면 `.env`에서 `BACKEND_PORT`를 바꾸고 프론트엔드 `.env`의 `VITE_BACKEND_ORIGIN`도 맞추기 |
| `Missing .env` | 3단계의 `cp .env.example .env`를 하지 않음. 또는 `setup.sh`를 먼저 실행 |
| `Backend is not running` (`database-data.sh`) | `setup.sh`가 끝나지 않았거나 컨테이너가 꺼짐. `docker compose ps`로 확인 후 `docker compose up -d` |
| 샘플 등록 거부 | 이미 데이터가 있음(정상). 새로 넣으려면 `docker compose down -v` 후 4단계부터 다시 |
| `cat ./seed-credentials.csv` 파일 없음 | 파일 이름 앞에 점이 있음. `cat ./.seed-credentials.csv` |
| HR AI 화면에 'AI 서버에 연결하지 못했습니다' 또는 `/health`에서 `"llm_configured":false` | 내 `.env`에 키가 없음(배포 서버의 키는 로컬로 들어오지 않음). 3단계의 'HR AI 키 넣기' 후 `bash ./setup/ai.sh` |
| 프론트엔드 `git clone`에서 Username, Password를 물음 | 비공개 저장소라 정상. 6단계의 로그인 방법 참고. GitHub 비밀번호는 git에서 쓸 수 없음 |
| HR AI가 'AI 서버에 연결하지 못했습니다' | 키가 틀렸거나 DeepSeek 잔액 부족. `docker compose logs ai`에서 `LLM_AUTH_FAILED`(키 오류), `LLM_HTTP_402`(잔액 부족) 등을 확인하고 팀장에게 알리기 |
| HR AI가 '인사관리자만 사용할 수 있습니다' | 사원 계정으로 로그인함. `admin01`로 로그인 |

## 프로젝트 구조

```text
Backend/
├── app/
│   ├── modules/             # 인증, 인사, 급여, 조직, 평가, 전자결재, 문서, AI 등
│   ├── cli.py               # DB 마이그레이션, 계정 관리, HR AI 권한 SQL 생성
│   ├── seed_demo.py         # 개발용 샘플 데이터 등록 로직
│   ├── config.py            # 환경 변수
│   ├── db.py                # DB 연결과 트랜잭션
│   ├── security.py          # 인증, 권한, CSRF
│   └── ...
├── ai/                      # HR AI(NL2SQL) FastAPI 서비스와 평가 도구(ai/eval)
├── database/                # 번호 순서대로 적용되는 SQL 마이그레이션
├── config/                  # Gunicorn 설정
├── setup/
│   ├── setup.sh             # 최초 설치와 실행 (아래 스크립트를 차례로 호출)
│   ├── database.sh          # DB 스키마 마이그레이션
│   ├── database-data.sh     # 개발용 샘플 데이터 일괄 등록
│   ├── ai.sh                # HR AI 읽기 전용 계정과 AI 서비스 기동
│   ├── llm-env.sh           # HR AI LLM 설정을 .env에 반영 (키 숨김 입력, 배포에서도 사용)
│   └── ai-eval.sh           # NL2SQL 평가 실행
├── .github/workflows/       # main 병합 시 서버 자동 배포
├── compose.yaml             # mysql, migrate, backend, ai 서비스
├── Dockerfile
├── requirements.txt         # Flask 쪽 Python 의존성
├── .env.example
└── wsgi.py
```

## 운영 주의 사항

`database/`의 기존 SQL은 수정하지 말고 새 번호로 마이그레이션 파일을 추가합니다. 적용 이력은 `schema_migrations` 테이블에서 관리합니다.

`.env`와 `.seed-credentials.csv`는 Git에 올리지 않습니다. 운영 DB에서 시드 스크립트를 실행하지 않습니다.

MySQL 볼륨과 발급 문서 볼륨은 정기적으로 백업해야 합니다. `docker compose down -v`는 볼륨의 실제 데이터를 삭제하므로 주의하세요.

`BACKEND_PORT=8080`은 모든 네트워크 인터페이스에 열리므로 같은 네트워크의 다른 기기에서도 접속할 수 있습니다. HR AI 포트는 내 컴퓨터(127.0.0.1)에서만 열립니다. 실제 서비스로 공개할 때는 HTTPS 리버스 프록시, 비밀정보 관리, 실제 도메인에 맞춘 CORS 설정이 필요합니다.

HR AI 기능은 `.env`에 LLM 설정이 있어야 작동합니다. LLM 설정이 없어도 다른 API는 정상 동작하며 AI 요청만 오류를 돌려줍니다. 노션에서 보류한 `SAL-04`, `EVAL-04` API는 구현되지 않았습니다.
