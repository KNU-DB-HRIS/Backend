-- 023: 역할 세분화 (HR 관리자 / 인사 담당자 / 인사 사원 / 사원)과 동작 권한
-- 지금까지는 HR_ADMIN 여부 하나로 검사했다. 이제 API마다 동작 권한(permissions)을 검사하고, 역할별 권한은 role_permissions로 준다
-- 표의 원본은 app/permissions.py (새 DB는 시드 add_roles가 같은 표로 만든다). 테이블 구조는 바꾸지 않고 행만 넣는다

-- 1) 역할 2개 추가 (기존 HR_ADMIN, EMPLOYEE는 그대로)
INSERT IGNORE INTO roles (role_code, role_name, description, is_active) VALUES
    ('HR_MANAGER', '인사 담당자', '인사 담당자: 인사, 급여, 결재 전체 조회, HR AI. 조직 변경·계열사·직원 삭제 제외', 1),
    ('HR_STAFF', '인사 사원', '인사 사원: 구성원 조회·등록·기본 정보 수정, 일정, 증명서 대리 발급, HR AI. 급여·발령·퇴사 제외', 1);

-- 2) 동작 권한 (메뉴 권한 MENU_*는 이미 있음)
INSERT IGNORE INTO permissions (permission_code, permission_name, resource_type, action_type, is_active) VALUES
    ('DASHBOARD_COMPANY', '회사 대시보드 조회', 'dashboard', 'READ', 1),
    ('EMPLOYEE_READ', '구성원 조회 (목록, 상세, 발령 이력, 구성원 검색)', 'employee', 'READ', 1),
    ('EMPLOYEE_CREATE', '직원 등록', 'employee', 'CREATE', 1),
    ('EMPLOYEE_UPDATE', '직원 기본 정보 수정', 'employee', 'UPDATE', 1),
    ('EMPLOYEE_ASSIGN', '인사 발령', 'employee', 'ASSIGN', 1),
    ('EMPLOYEE_TERMINATE', '퇴사 처리', 'employee', 'TERMINATE', 1),
    ('EMPLOYEE_DELETE', '오등록 직원 삭제', 'employee', 'DELETE', 1),
    ('ROLE_MANAGE', '계정 역할 변경', 'user', 'UPDATE', 1),
    ('SALARY_READ', '다른 직원 급여 조회', 'salary', 'READ', 1),
    ('SALARY_UPDATE', '급여 변경 등록', 'salary', 'UPDATE', 1),
    ('ORG_READ', '조직, 회사 정보 조회', 'organization', 'READ', 1),
    ('ORG_MANAGE', '조직, 회사 정보 등록·수정·사용 중지', 'organization', 'MANAGE', 1),
    ('COMPANY_MANAGE', '계열사 조회·등록', 'company', 'MANAGE', 1),
    ('EVALUATION_READ', '평가 회차, 진행 현황, 대상자 조회', 'evaluation', 'READ', 1),
    ('APPROVAL_READ_ALL', '회사 전체 결재 문서 조회', 'approval', 'READ', 1),
    ('DOCUMENT_ISSUE_OTHERS', '다른 직원 증명서 발급, 발급 내역 조회', 'document', 'ISSUE', 1),
    ('EVENT_MANAGE', '일정 등록·수정·삭제, 회사 일정 전체 조회', 'event', 'MANAGE', 1),
    ('AI_QUERY', 'HR AI 질의', 'ai', 'QUERY', 1);
INSERT IGNORE INTO permissions (permission_code, permission_name, resource_type, action_type, is_active) VALUES
    ('MENU_DASHBOARD', '대시보드', 'menu', 'VIEW', 1),
    ('MENU_EMPLOYEES', '인사 관리', 'menu', 'VIEW', 1),
    ('MENU_PAYROLL', '급여 관리', 'menu', 'VIEW', 1),
    ('MENU_ORGANIZATION', '조직 관리', 'menu', 'VIEW', 1),
    ('MENU_EVALUATION', '평가 관리', 'menu', 'VIEW', 1),
    ('MENU_DOCUMENTS', '전자 문서', 'menu', 'VIEW', 1),
    ('MENU_SCHEDULE', '일정', 'menu', 'VIEW', 1),
    ('MENU_AI', 'HR AI', 'menu', 'VIEW', 1);

-- 3) 역할별 권한. 역할이 아직 없는 새 DB에서는 아무 행도 들어가지 않고, 시드가 같은 표로 넣는다
-- HR_ADMIN: 26개
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM roles r JOIN permissions p
    ON p.permission_code IN ('AI_QUERY', 'APPROVAL_READ_ALL', 'COMPANY_MANAGE', 'DASHBOARD_COMPANY', 'DOCUMENT_ISSUE_OTHERS', 'EMPLOYEE_ASSIGN', 'EMPLOYEE_CREATE', 'EMPLOYEE_DELETE', 'EMPLOYEE_READ', 'EMPLOYEE_TERMINATE', 'EMPLOYEE_UPDATE', 'EVALUATION_READ', 'EVENT_MANAGE', 'MENU_AI', 'MENU_DASHBOARD', 'MENU_DOCUMENTS', 'MENU_EMPLOYEES', 'MENU_EVALUATION', 'MENU_ORGANIZATION', 'MENU_PAYROLL', 'MENU_SCHEDULE', 'ORG_MANAGE', 'ORG_READ', 'ROLE_MANAGE', 'SALARY_READ', 'SALARY_UPDATE')
WHERE r.role_code = 'HR_ADMIN' AND r.is_active = 1 AND p.is_active = 1;
-- HR_MANAGER: 22개
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM roles r JOIN permissions p
    ON p.permission_code IN ('AI_QUERY', 'APPROVAL_READ_ALL', 'DASHBOARD_COMPANY', 'DOCUMENT_ISSUE_OTHERS', 'EMPLOYEE_ASSIGN', 'EMPLOYEE_CREATE', 'EMPLOYEE_READ', 'EMPLOYEE_TERMINATE', 'EMPLOYEE_UPDATE', 'EVALUATION_READ', 'EVENT_MANAGE', 'MENU_AI', 'MENU_DASHBOARD', 'MENU_DOCUMENTS', 'MENU_EMPLOYEES', 'MENU_EVALUATION', 'MENU_ORGANIZATION', 'MENU_PAYROLL', 'MENU_SCHEDULE', 'ORG_READ', 'SALARY_READ', 'SALARY_UPDATE')
WHERE r.role_code = 'HR_MANAGER' AND r.is_active = 1 AND p.is_active = 1;
-- HR_STAFF: 15개
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM roles r JOIN permissions p
    ON p.permission_code IN ('AI_QUERY', 'DASHBOARD_COMPANY', 'DOCUMENT_ISSUE_OTHERS', 'EMPLOYEE_CREATE', 'EMPLOYEE_READ', 'EMPLOYEE_UPDATE', 'EVENT_MANAGE', 'MENU_AI', 'MENU_DASHBOARD', 'MENU_DOCUMENTS', 'MENU_EMPLOYEES', 'MENU_EVALUATION', 'MENU_ORGANIZATION', 'MENU_SCHEDULE', 'ORG_READ')
WHERE r.role_code = 'HR_STAFF' AND r.is_active = 1 AND p.is_active = 1;
-- EMPLOYEE: 4개
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM roles r JOIN permissions p
    ON p.permission_code IN ('MENU_DASHBOARD', 'MENU_DOCUMENTS', 'MENU_EVALUATION', 'MENU_SCHEDULE')
WHERE r.role_code = 'EMPLOYEE' AND r.is_active = 1 AND p.is_active = 1;
