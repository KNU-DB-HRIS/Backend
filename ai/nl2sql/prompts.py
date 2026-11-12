"""프롬프트 두 종류 (과제 요구: 같은 질문에 Simple vs 보강 방식 비교)

- simple   : 테이블·열 이름만 (기본 Schema)
- enhanced : + PK/FK·관계·열 의미·코드값·업무 용어·집계 기준·예시

두 방식 모두 공통 규칙(서버 실행 조건·출력 형식)은 같게 줘서, 차이가 '스키마 지식' 하나에서만 나오게 한다.
업무 용어(장기근속 3년, 신입 1년, 최근 90일 등)는 팀 합의 전 제안값 → GLOSSARY만 고치면 됨.
"""
import json

COMMON_RULES = """너는 HR 시스템의 MySQL 8 SQL 생성기다. 사용자의 한국어 질문을 읽기 전용 SELECT 한 문장으로 바꾼다.

[실행 규칙]
- SELECT 문 하나만. WITH(CTE)·UNION·INSERT·UPDATE·DELETE·주석(--, /* */, #) 금지
- 아래 스키마의 테이블·열만 사용. SELECT * 금지(COUNT(*)만 허용). 열 이름을 직접 적을 것
- 사용 가능한 함수: {functions}. 그 밖의 함수(NOW, DATE_SUB, DATE_FORMAT, GROUP_CONCAT, 윈도 함수 등) 금지. 오늘 날짜는 CURRENT_DATE
- company_id 조건은 쓰지 말 것(서버가 회사 범위를 자동으로 건다)
- LIMIT·OFFSET 쓰지 말 것(서버가 최대 200행으로 자른다). 순서가 의미 있으면 ORDER BY
- 결과 열 별칭은 백틱으로 감싼 한국어 (예: AS `재직 인원`)

[출력 형식] JSON 객체 하나만, 다른 글 없이
{{"status": "OK" | "NEEDS_CLARIFICATION" | "OUT_OF_SCOPE", "sql": "SELECT ..." 또는 null, "answer": "한국어 한두 문장"}}
- OK: sql 필수. answer에는 무엇을 어떤 기준으로 조회했는지(가정 포함). 결과 숫자는 아직 모르니 지어내지 말 것
- NEEDS_CLARIFICATION: 질문만으로 대상을 정할 수 없을 때. sql은 null, answer에 되물을 질문
- OUT_OF_SCOPE: 스키마로 답할 수 없는 정보를 물을 때. sql은 null, answer에 이유"""

TABLE_DOCS = {
    "employees": ("직원 1명 = 1행. 퇴사자도 행이 남아 있음", {
        "employee_id": "PK",
        "employee_no": "사번 (예: EMP001)",
        "employee_name": "이름",
        "hire_date": "입사일",
        "termination_date": "퇴사일. 재직·휴직이면 NULL",
        "employment_type": "고용 형태 코드: FULL_TIME(정규직), CONTRACT(계약직), INTERN(인턴)",
        "employment_status": "재직 상태 코드: ACTIVE(재직), ON_LEAVE(휴직), TERMINATED(퇴사)",
        "department_id": "FK → departments.department_id (소속 부서)",
        "position_id": "FK → positions.position_id (직급)",
        "job_id": "FK → jobs.job_id (직무)",
        "job_title_id": "FK → job_titles.job_title_id (직책). 직책 없으면 NULL",
    }),
    "departments": ("부서", {
        "department_id": "PK",
        "parent_department_id": "FK → departments.department_id (상위 부서). NULL이면 최상위",
        "department_code": "부서 코드 (예: DEP-DEV)",
        "department_name": "부서명 (예: 개발팀)",
        "is_active": "1 = 사용 중, 0 = 사용 중지",
    }),
    "positions": ("직급 (사원 < 대리 < 과장 < 차장 < 부장)", {
        "position_id": "PK",
        "position_name": "직급명",
        "position_level": "숫자가 클수록 높은 직급",
        "is_active": "1 = 사용 중",
    }),
    "jobs": ("직무 (하는 일)", {
        "job_id": "PK",
        "job_name": "직무명 (예: 서비스 개발)",
        "job_family": "직군",
        "job_category": "직무 분류",
        "is_active": "1 = 사용 중",
    }),
    "job_titles": ("직책 (팀장, 팀원 등 맡은 역할). 직급과 다른 개념", {
        "job_title_id": "PK",
        "job_title_name": "직책명",
        "is_active": "1 = 사용 중",
    }),
    "vw_nl_employee_directory": ("직원에 부서명·직급명·직무명·직책명을 미리 붙인 뷰. 퇴사자 포함. 이름 조회 시 JOIN 대신 써도 됨", {
        "employment_status": "ACTIVE / ON_LEAVE / TERMINATED",
    }),
    "vw_nl_org_headcounts": ("부서별 재직(ACTIVE) 인원을 미리 센 뷰. 휴직자는 세지 않음", {
        "active_headcount": "그 부서의 재직 인원",
    }),
}

GLOSSARY = """[업무 용어와 집계 기준]
- 직원·인원·사람 수: 따로 말이 없으면 재직(ACTIVE)만
- 전체 구성원: 재직 + 휴직 (ACTIVE, ON_LEAVE). 퇴사자 제외
- '퇴사자 포함', '전체 이력': 상태 조건 없이 전부
- 휴직자 = ON_LEAVE, 퇴사자 = TERMINATED
- 근속 연수 = TIMESTAMPDIFF(YEAR, hire_date, CURRENT_DATE), 근속 개월 = TIMESTAMPDIFF(MONTH, hire_date, CURRENT_DATE)
- 신입(신규 입사자): 입사 1년 미만 재직자 → TIMESTAMPDIFF(YEAR, hire_date, CURRENT_DATE) < 1
- 장기근속자: 근속 3년 이상 재직자
- 최근 입사자(기간 말이 없을 때): 최근 90일 → DATEDIFF(CURRENT_DATE, hire_date) <= 90. answer에 기준을 적을 것
- 올해 입사자: YEAR(hire_date) = YEAR(CURRENT_DATE)
- 직급(사원·대리·과장·차장·부장)은 positions, 직책(팀장·팀원)은 job_titles. 섞지 말 것
- '대리 이상' 같은 직급 범위는 position_level 비교
- 부서별 집계: 부서명으로 묶고 사용 중(is_active = 1) 부서만
- 급여·연봉·연락처·주소·생년월일·평가·근태는 AI 조회 범위 밖 → OUT_OF_SCOPE
- 앞 대화 없이 '그 사람', '거기'처럼 가리키는 대상이 없으면 NEEDS_CLARIFICATION"""

EXAMPLES = [
    ("디자인팀 팀장 이름 알려줘", {
        "status": "OK",
        "sql": "SELECT e.employee_name AS `이름` FROM employees e JOIN departments d ON d.department_id = e.department_id "
               "JOIN job_titles t ON t.job_title_id = e.job_title_id WHERE d.department_name = '디자인팀' "
               "AND t.job_title_name = '팀장' AND e.employment_status = 'ACTIVE'",
        "answer": "디자인팀에서 직책이 팀장인 재직자를 조회했습니다.",
    }),
    ("직급별 재직 인원", {
        "status": "OK",
        "sql": "SELECT p.position_name AS `직급`, COUNT(*) AS `재직 인원` FROM employees e JOIN positions p "
               "ON p.position_id = e.position_id WHERE e.employment_status = 'ACTIVE' "
               "GROUP BY p.position_name, p.position_level ORDER BY p.position_level DESC",
        "answer": "직급별 재직(ACTIVE) 인원을 높은 직급부터 셌습니다.",
    }),
    ("직원 연락처 알려줘", {
        "status": "OUT_OF_SCOPE", "sql": None,
        "answer": "연락처는 HR AI 조회 범위가 아닙니다. 인사관리 화면에서 확인해 주세요.",
    }),
]


def _schema_lines(schema: dict[str, list[str]]) -> str:
    return "\n".join(f"- {t}({', '.join(cols)})" for t, cols in schema.items())


def _enhanced_lines(schema: dict[str, list[str]]) -> str:
    out = []
    for table, cols in schema.items():
        desc, col_docs = TABLE_DOCS.get(table, ("", {}))
        out.append(f"- {table}: {desc}" if desc else f"- {table}")
        for c in cols:
            if c in col_docs:
                out.append(f"  - {c}: {col_docs[c]}")
    joins = [
        "employees.department_id = departments.department_id",
        "employees.position_id = positions.position_id",
        "employees.job_id = jobs.job_id",
        "employees.job_title_id = job_titles.job_title_id (LEFT JOIN: 직책 없는 직원 있음)",
        "departments.parent_department_id = departments.department_id (상위 부서)",
    ]
    present = [j for j in joins if all(t.split(".")[0] in schema for t in j.split(" (")[0].split(" = "))]
    if present:
        out.append("\n[관계]\n" + "\n".join(f"- {j}" for j in present))
    return "\n".join(out)


def build_messages(mode: str, question: str, schema: dict[str, list[str]], functions: list[str]) -> list[dict]:
    system = COMMON_RULES.format(functions=", ".join(functions)) + "\n\n[스키마]\n" + _schema_lines(schema)
    if mode == "enhanced":
        system += "\n\n[테이블·열 설명]\n" + _enhanced_lines(schema) + "\n\n" + GLOSSARY
        system += "\n\n[예시]\n" + "\n".join(
            f"질문: {q}\n{json.dumps(a, ensure_ascii=False)}" for q, a in EXAMPLES)
    return [{"role": "system", "content": system}, {"role": "user", "content": question}]


def repair_message(problems: list[str]) -> dict:
    return {"role": "user", "content": "방금 SQL이 서버 규칙에 걸렸다: " + "; ".join(problems)
            + ". 규칙을 지켜 같은 JSON 형식으로 다시 답하라."}
