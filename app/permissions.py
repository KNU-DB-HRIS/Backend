"""역할과 권한 (RBAC)

역할은 사용자마다 하나(user_roles). 화면 메뉴(MENU_*)와 동작 권한을 role_permissions로 준다.
서버는 API마다 동작 권한을 검사하고(require_auth(permission=...)), 메뉴 숨김은 보조 수단이다.

같은 표를 두 곳에서 쓴다
- 새 DB: 시드(add_roles)가 이 표로 roles, permissions, role_permissions를 만든다
- 운영 DB: database/023_role_permissions.sql 이 같은 행을 넣는다 (tests/e2e_roles.py가 DB와 이 표를 대조)
"""

ROLES = (
    ("HR_ADMIN", "HR 관리자"),
    ("HR_MANAGER", "인사 담당자"),
    ("HR_STAFF", "인사 사원"),
    ("EMPLOYEE", "사원"),
)
ROLE_CODES = tuple(code for code, _ in ROLES)
# 사용자에게 역할이 여러 개 남아 있을 때 화면 표시와 판정에 쓰는 순서 (앞이 높음)
ROLE_RANK = {code: rank for rank, code in enumerate(ROLE_CODES)}

MENUS = (
    ("DASHBOARD", "대시보드"),
    ("EMPLOYEES", "인사 관리"),
    ("PAYROLL", "급여 관리"),
    ("ORGANIZATION", "조직 관리"),
    ("EVALUATION", "평가 관리"),
    ("DOCUMENTS", "전자 문서"),
    ("SCHEDULE", "일정"),
    ("AI", "HR AI"),
)

# code: (이름, resource_type, action_type)
ACTIONS = {
    "DASHBOARD_COMPANY": ("회사 대시보드 조회", "dashboard", "READ"),
    "EMPLOYEE_READ": ("구성원 조회 (목록, 상세, 발령 이력, 구성원 검색)", "employee", "READ"),
    "EMPLOYEE_CREATE": ("직원 등록", "employee", "CREATE"),
    "EMPLOYEE_UPDATE": ("직원 기본 정보 수정", "employee", "UPDATE"),
    "EMPLOYEE_ASSIGN": ("인사 발령", "employee", "ASSIGN"),
    "EMPLOYEE_TERMINATE": ("퇴사 처리", "employee", "TERMINATE"),
    "EMPLOYEE_DELETE": ("오등록 직원 삭제", "employee", "DELETE"),
    "ROLE_MANAGE": ("계정 역할 변경", "user", "UPDATE"),
    "SALARY_READ": ("다른 직원 급여 조회", "salary", "READ"),
    "SALARY_UPDATE": ("급여 변경 등록", "salary", "UPDATE"),
    "ORG_READ": ("조직, 회사 정보 조회", "organization", "READ"),
    "ORG_MANAGE": ("조직, 회사 정보 등록·수정·사용 중지", "organization", "MANAGE"),
    "COMPANY_MANAGE": ("계열사 조회·등록", "company", "MANAGE"),
    "EVALUATION_READ": ("평가 회차, 진행 현황, 대상자 조회", "evaluation", "READ"),
    "APPROVAL_READ_ALL": ("회사 전체 결재 문서 조회", "approval", "READ"),
    "DOCUMENT_ISSUE_OTHERS": ("다른 직원 증명서 발급, 발급 내역 조회", "document", "ISSUE"),
    "EVENT_MANAGE": ("일정 등록·수정·삭제, 회사 일정 전체 조회", "event", "MANAGE"),
    "AI_QUERY": ("HR AI 질의", "ai", "QUERY"),
}

_EMPLOYEE_MENUS = {"MENU_DASHBOARD", "MENU_EVALUATION", "MENU_DOCUMENTS", "MENU_SCHEDULE"}
GRANTS = {
    "HR_ADMIN": {f"MENU_{m}" for m, _ in MENUS} | set(ACTIONS),
    "HR_MANAGER": _EMPLOYEE_MENUS | {"MENU_EMPLOYEES", "MENU_PAYROLL", "MENU_ORGANIZATION", "MENU_AI"} | {
        "DASHBOARD_COMPANY", "EMPLOYEE_READ", "EMPLOYEE_CREATE", "EMPLOYEE_UPDATE", "EMPLOYEE_ASSIGN",
        "EMPLOYEE_TERMINATE", "SALARY_READ", "SALARY_UPDATE", "ORG_READ", "EVALUATION_READ",
        "APPROVAL_READ_ALL", "DOCUMENT_ISSUE_OTHERS", "EVENT_MANAGE", "AI_QUERY",
    },
    "HR_STAFF": _EMPLOYEE_MENUS | {"MENU_EMPLOYEES", "MENU_ORGANIZATION", "MENU_AI"} | {
        "DASHBOARD_COMPANY", "EMPLOYEE_READ", "EMPLOYEE_CREATE", "EMPLOYEE_UPDATE", "ORG_READ",
        "DOCUMENT_ISSUE_OTHERS", "EVENT_MANAGE", "AI_QUERY",
    },
    "EMPLOYEE": set(_EMPLOYEE_MENUS),
}

# 급여가 들어 있는 문서: 다른 직원 것은 SALARY_READ도 있어야 발급·조회
SALARY_DOCUMENTS = ("PAYSLIP", "WITHHOLDING")


def all_permissions():
    """(code, name, resource_type, action_type) 전체"""
    rows = [(f"MENU_{m}", name, "menu", "VIEW") for m, name in MENUS]
    rows += [(code, *meta) for code, meta in ACTIONS.items()]
    return rows
