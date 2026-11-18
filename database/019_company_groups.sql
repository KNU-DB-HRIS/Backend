-- 019: 계열사(멀티 회사) 관리
-- 1) company_groups: 계열사 묶음 (그룹 1 : 회사 N, 평면 구조)
-- 2) user_company_roles: 소속 회사 밖의 회사에서 사용자가 갖는 역할 (사용자 x 회사 x 역할)
--    소속 회사의 역할은 기존 user_roles 그대로 사용한다
-- 3) auth_sessions.active_company_id: 세션별 현재 회사 (NULL이면 소속 회사)

CREATE TABLE company_groups (
    group_id BIGINT NOT NULL AUTO_INCREMENT,
    group_name VARCHAR(100) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (group_id),
    UNIQUE KEY uq_company_groups_group_name (group_name)
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

ALTER TABLE companies
    ADD COLUMN group_id BIGINT NULL AFTER company_id,
    ADD KEY idx_companies_group_id (group_id),
    ADD CONSTRAINT fk_companies_group_id FOREIGN KEY (group_id)
        REFERENCES company_groups (group_id) ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE user_company_roles (
    user_id BIGINT NOT NULL,
    company_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (user_id, company_id, role_id),
    KEY idx_user_company_roles_company_id (company_id),
    KEY idx_user_company_roles_role_id (role_id),
    CONSTRAINT fk_user_company_roles_user_id FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_user_company_roles_company_id FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_user_company_roles_role_id FOREIGN KEY (role_id)
        REFERENCES roles (role_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

ALTER TABLE auth_sessions
    ADD COLUMN active_company_id BIGINT NULL,
    ADD KEY idx_auth_sessions_active_company_id (active_company_id),
    ADD CONSTRAINT fk_auth_sessions_active_company_id FOREIGN KEY (active_company_id)
        REFERENCES companies (company_id) ON DELETE RESTRICT ON UPDATE RESTRICT;
