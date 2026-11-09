ALTER TABLE departments DROP FOREIGN KEY fk_departments_manager_employee;
ALTER TABLE departments ADD CONSTRAINT fk_departments_manager_company
FOREIGN KEY (company_id, manager_employee_id) REFERENCES employees(company_id, employee_id)
ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE approval_requests DROP CHECK ck_approval_requests_status;
UPDATE approval_requests SET status='IN_PROGRESS' WHERE status='PENDING';
ALTER TABLE approval_requests MODIFY status VARCHAR(20) NOT NULL DEFAULT 'DRAFT';
ALTER TABLE approval_requests MODIFY content TEXT NULL;
ALTER TABLE approval_requests ADD CONSTRAINT ck_approval_requests_status
CHECK (status IN ('DRAFT','IN_PROGRESS','APPROVED','REJECTED'));

ALTER TABLE approval_steps DROP CHECK ck_approval_steps_status;
UPDATE approval_steps s JOIN approval_requests r ON r.approval_request_id=s.approval_request_id
SET s.status='SKIPPED' WHERE r.status='REJECTED' AND s.status='PENDING';
UPDATE approval_steps s JOIN
(SELECT approval_request_id, MIN(step_order) AS first_pending FROM
 (SELECT approval_request_id, step_order FROM approval_steps WHERE status='PENDING') p
 GROUP BY approval_request_id) current_step
ON current_step.approval_request_id=s.approval_request_id
SET s.status='WAITING' WHERE s.status='PENDING' AND s.step_order>current_step.first_pending;
ALTER TABLE approval_steps ADD CONSTRAINT ck_approval_steps_status
CHECK (status IN ('WAITING','PENDING','APPROVED','REJECTED','SKIPPED'));

ALTER TABLE audit_logs DROP CHECK ck_audit_logs_action_type;
ALTER TABLE audit_logs ADD COLUMN company_id BIGINT NULL;
ALTER TABLE audit_logs ADD KEY idx_audit_logs_company_created (company_id, created_at);

CREATE TABLE auth_sessions (
    session_id CHAR(32) PRIMARY KEY,
    user_id BIGINT NOT NULL,
    refresh_jti_hash CHAR(64) NOT NULL,
    csrf_hash CHAR(64) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    revoked_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_auth_sessions_user (user_id),
    KEY idx_auth_sessions_expiry (expires_at),
    CONSTRAINT fk_auth_sessions_user FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE auth_login_attempts (
    attempt_key CHAR(64) PRIMARY KEY,
    failures INT NOT NULL DEFAULT 0,
    window_started_at DATETIME(6) NOT NULL
);

CREATE TABLE uploaded_logos (
    logo_id CHAR(32) PRIMARY KEY,
    company_id BIGINT NOT NULL,
    file_name VARCHAR(100) NOT NULL,
    media_type VARCHAR(50) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_uploaded_logos_company FOREIGN KEY(company_id) REFERENCES companies(company_id)
);
