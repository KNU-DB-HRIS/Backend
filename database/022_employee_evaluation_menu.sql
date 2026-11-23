-- 022: 일반 사원에게도 평가 메뉴. 사원은 '내가 할 평가'(GET /me/evaluation-tasks)를 보고 단계 평가를 제출함
-- 회차 목록, 현황, 대상자 목록 API는 계속 HR_ADMIN 전용. 역할이 아직 없는 새 DB는 시드(add_roles)가 같은 권한을 만든다
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r JOIN permissions p ON p.permission_code = 'MENU_EVALUATION'
WHERE r.role_code = 'EMPLOYEE' AND r.is_active = 1 AND p.is_active = 1;
