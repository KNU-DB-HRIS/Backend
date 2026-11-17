-- 021: 일반 사원에게도 대시보드 메뉴 (사원은 개인 대시보드를 보고, 회사 전체 지표 API GET /dashboard는 계속 HR_ADMIN 전용)
-- 역할이 아직 없는 새 DB는 시드(add_roles)가 같은 권한을 만든다
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r JOIN permissions p ON p.permission_code = 'MENU_DASHBOARD'
WHERE r.role_code = 'EMPLOYEE' AND r.is_active = 1 AND p.is_active = 1;
