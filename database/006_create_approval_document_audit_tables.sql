CREATE TABLE approval_requests (
    approval_request_id BIGINT NOT NULL AUTO_INCREMENT,
    request_type VARCHAR(30) NOT NULL,
    reference_id BIGINT NULL,
    requester_user_id BIGINT NOT NULL,
    title VARCHAR(100) NOT NULL,
    content VARCHAR(500) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    requested_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    completed_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (approval_request_id),
    KEY idx_approval_requests_requester_user_id_requested_at (requester_user_id, requested_at),
    KEY idx_approval_requests_status_requested_at (status, requested_at),
    KEY idx_approval_requests_request_type_reference_id (request_type, reference_id),
    CONSTRAINT fk_approval_requests_requester_user_id FOREIGN KEY (requester_user_id) REFERENCES users (user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT ck_approval_requests_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'))
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE approval_steps (
    approval_step_id BIGINT NOT NULL AUTO_INCREMENT,
    approval_request_id BIGINT NOT NULL,
    step_order INT NOT NULL,
    approver_user_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    comments VARCHAR(500) NULL,
    decided_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (approval_step_id),
    UNIQUE KEY uq_approval_steps_approval_request_id_step_order (approval_request_id, step_order),
    KEY idx_approval_steps_approver_user_id_status (approver_user_id, status),
    CONSTRAINT fk_approval_steps_approval_request_id FOREIGN KEY (approval_request_id) REFERENCES approval_requests (approval_request_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_approval_steps_approver_user_id FOREIGN KEY (approver_user_id) REFERENCES users (user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT ck_approval_steps_order CHECK (step_order > 0),
    CONSTRAINT ck_approval_steps_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'))
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE documents (
    document_id BIGINT NOT NULL AUTO_INCREMENT,
    employee_id BIGINT NOT NULL,
    document_type VARCHAR(30) NOT NULL,
    file_name VARCHAR(100) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    issued_by_user_id BIGINT NOT NULL,
    issued_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (document_id),
    KEY idx_documents_employee_id_issued_at (employee_id, issued_at),
    KEY idx_documents_issued_by_user_id (issued_by_user_id),
    CONSTRAINT fk_documents_employee_id FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_documents_issued_by_user_id FOREIGN KEY (issued_by_user_id) REFERENCES users (user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE audit_logs (
    audit_log_id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NULL,
    action_type VARCHAR(30) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id BIGINT NULL,
    before_data JSON NULL,
    after_data JSON NULL,
    ip_address VARCHAR(45) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (audit_log_id),
    KEY idx_audit_logs_user_id_created_at (user_id, created_at),
    KEY idx_audit_logs_resource_type_resource_id_created_at (resource_type, resource_id, created_at),
    KEY idx_audit_logs_created_at (created_at),
    CONSTRAINT fk_audit_logs_user_id FOREIGN KEY (user_id) REFERENCES users (user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT ck_audit_logs_action_type CHECK (action_type IN ('INSERT', 'UPDATE', 'DELETE'))
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
