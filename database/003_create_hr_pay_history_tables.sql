CREATE TABLE assignment_history (
    assignment_history_id BIGINT NOT NULL AUTO_INCREMENT,
    employee_id BIGINT NOT NULL,
    action_type VARCHAR(20) NOT NULL,
    action_date DATE NOT NULL,
    effective_date DATE NULL,
    from_department_id BIGINT NULL,
    to_department_id BIGINT NULL,
    from_position_id BIGINT NULL,
    to_position_id BIGINT NOT NULL,
    from_job_id BIGINT NULL,
    to_job_id BIGINT NULL,
    from_job_title_id BIGINT NULL,
    to_job_title_id BIGINT NULL,
    reason VARCHAR(300) NOT NULL,
    document_url VARCHAR(500) NULL,
    created_by_user_id BIGINT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (assignment_history_id),
    KEY idx_assignment_history_employee_id_effective_date_action_date (employee_id, effective_date, action_date),
    KEY idx_assignment_history_action_date (action_date),
    CONSTRAINT fk_assignment_history_employee_id FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_assignment_history_from_department_id FOREIGN KEY (from_department_id) REFERENCES departments (department_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_assignment_history_to_department_id FOREIGN KEY (to_department_id) REFERENCES departments (department_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_assignment_history_from_position_id FOREIGN KEY (from_position_id) REFERENCES positions (position_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_assignment_history_to_position_id FOREIGN KEY (to_position_id) REFERENCES positions (position_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_assignment_history_from_job_id FOREIGN KEY (from_job_id) REFERENCES jobs (job_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_assignment_history_to_job_id FOREIGN KEY (to_job_id) REFERENCES jobs (job_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_assignment_history_from_job_title_id FOREIGN KEY (from_job_title_id) REFERENCES job_titles (job_title_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_assignment_history_to_job_title_id FOREIGN KEY (to_job_title_id) REFERENCES job_titles (job_title_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE salary_history (
    salary_history_id BIGINT NOT NULL AUTO_INCREMENT,
    employee_id BIGINT NOT NULL,
    previous_salary DECIMAL(15,2) NULL,
    new_salary DECIMAL(15,2) NOT NULL,
    effective_date DATE NOT NULL,
    reason VARCHAR(200) NULL,
    changed_by_user_id BIGINT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (salary_history_id),
    KEY idx_salary_history_employee_id_effective_date (employee_id, effective_date),
    CONSTRAINT fk_salary_history_employee_id FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT ck_salary_history_previous CHECK (previous_salary IS NULL OR previous_salary >= 0),
    CONSTRAINT ck_salary_history_new CHECK (new_salary >= 0)
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
