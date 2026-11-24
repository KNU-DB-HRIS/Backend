-- 024: 첫 로그인 비밀번호 변경과 관리자 비밀번호 초기화
-- 관리자가 임시 비밀번호로 만든 계정(직원 등록 시 계정 발급, 비밀번호 초기화)은 첫 로그인 때 새 비밀번호를 정해야
-- 다른 화면과 API를 쓸 수 있다 (password_change_required). 기존 계정은 그대로 쓰도록 FALSE로 시작한다.
-- 비밀번호 초기화는 HR 관리자만 (동작 권한 PASSWORD_RESET, app/permissions.py 표와 같음).

ALTER TABLE users
    ADD COLUMN password_change_required BOOLEAN NOT NULL DEFAULT FALSE AFTER status,
    ADD COLUMN password_changed_at DATETIME(6) NULL AFTER password_change_required;

INSERT IGNORE INTO permissions (permission_code, permission_name, resource_type, action_type, is_active) VALUES
    ('PASSWORD_RESET', '계정 비밀번호 초기화', 'user', 'RESET', 1);

INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM roles r JOIN permissions p
    ON p.permission_code = 'PASSWORD_RESET'
WHERE r.role_code = 'HR_ADMIN' AND r.is_active = 1 AND p.is_active = 1;
