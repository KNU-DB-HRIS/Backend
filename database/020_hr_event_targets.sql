-- 020: 일정 관리 - 표시 대상 조직
-- hr_events에 설명, 표시 범위(COMPANY 전사 | DEPARTMENTS 지정 조직), 작성자, 수정 시각을 추가하고
-- hr_event_departments(일정 N : 부서 M)로 표시 대상 조직을 저장한다.
-- 사원에게 보일지는 조회할 때 '내 부서 + 상위 부서'로 계산하므로 입사, 부서 이동이 자동 반영된다.
-- 기존 일정은 scope='COMPANY'(전사)로 남고 target 문장은 표시용으로 유지된다.

ALTER TABLE hr_events
    ADD COLUMN description VARCHAR(1000) NULL AFTER title,
    ADD COLUMN scope VARCHAR(20) NOT NULL DEFAULT 'COMPANY' AFTER location,
    ADD COLUMN created_by_user_id BIGINT NULL AFTER target,
    ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at,
    ADD UNIQUE KEY uq_hr_events_company_id_event_id (company_id, event_id),
    ADD KEY idx_hr_events_company_id_start_at (company_id, start_at),
    ADD CONSTRAINT ck_hr_events_scope CHECK (scope IN ('COMPANY', 'DEPARTMENTS')),
    ADD CONSTRAINT ck_hr_events_range CHECK (end_at IS NULL OR end_at >= start_at),
    ADD CONSTRAINT fk_hr_events_created_by_user_id FOREIGN KEY (created_by_user_id)
        REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT;

-- 기존 일정은 수정된 적이 없으므로 수정 시각을 등록 시각으로 맞춘다 (새 열의 기본값은 마이그레이션 시각이라 '수정됨'으로 보이는 것 방지)
UPDATE hr_events SET updated_at = created_at;

-- 일정의 표시 대상 조직. company_id를 함께 둬서 '같은 회사의 일정과 부서끼리만' 연결되도록 DB가 보장
CREATE TABLE hr_event_departments (
    event_id BIGINT NOT NULL,
    company_id BIGINT NOT NULL,
    department_id BIGINT NOT NULL,
    include_children BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (event_id, department_id),
    KEY idx_hr_event_departments_company_id_department_id (company_id, department_id),
    CONSTRAINT fk_hr_event_departments_event FOREIGN KEY (company_id, event_id)
        REFERENCES hr_events (company_id, event_id) ON DELETE CASCADE ON UPDATE RESTRICT,
    CONSTRAINT fk_hr_event_departments_department FOREIGN KEY (company_id, department_id)
        REFERENCES departments (company_id, department_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

-- '일정' 메뉴: 인사관리자와 사원 모두 (역할이 아직 없는 새 DB는 시드가 같은 권한을 만든다)
INSERT IGNORE INTO permissions (permission_code, permission_name, resource_type, action_type, is_active)
VALUES ('MENU_SCHEDULE', '일정', 'menu', 'VIEW', 1);

INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r JOIN permissions p ON p.permission_code = 'MENU_SCHEDULE'
WHERE r.role_code IN ('HR_ADMIN', 'EMPLOYEE') AND r.is_active = 1 AND p.is_active = 1;
