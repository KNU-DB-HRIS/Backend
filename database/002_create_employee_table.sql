CREATE TABLE employees (
    employee_id BIGINT NOT NULL AUTO_INCREMENT,
    company_id BIGINT NOT NULL,
    employee_no VARCHAR(20) NOT NULL,
    employee_name VARCHAR(50) NOT NULL,
    birth_date DATE NULL,
    gender VARCHAR(10) NULL,
    phone VARCHAR(20) NULL,
    email VARCHAR(100) NULL,
    hire_date DATE NOT NULL,
    termination_date DATE NULL,
    employment_type VARCHAR(20) NOT NULL,
    employment_status VARCHAR(20) NOT NULL,
    department_id BIGINT NOT NULL,
    position_id BIGINT NOT NULL,
    job_id BIGINT NOT NULL,
    job_title_id BIGINT NULL,
    current_salary DECIMAL(15,2) NULL,
    profile_image_url VARCHAR(500) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (employee_id),
    UNIQUE KEY uq_employees_company_id_employee_no (company_id, employee_no),
    UNIQUE KEY uq_employees_email (email),
    UNIQUE KEY uq_employees_company_id_employee_id (company_id, employee_id),
    UNIQUE KEY uq_employees_company_id_department_id_employee_id (company_id, department_id, employee_id),
    KEY idx_employees_employee_name (employee_name),
    KEY idx_employees_company_department_position_employment_status (company_id, department_id, position_id, employment_status),
    KEY idx_employees_company_id_position_id (company_id, position_id),
    KEY idx_employees_company_id_job_id (company_id, job_id),
    KEY idx_employees_company_id_job_title_id (company_id, job_title_id),
    CONSTRAINT fk_employees_company_id FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_employees_company_id_department_id FOREIGN KEY (company_id, department_id)
        REFERENCES departments (company_id, department_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_employees_company_id_position_id FOREIGN KEY (company_id, position_id)
        REFERENCES positions (company_id, position_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_employees_company_id_job_id FOREIGN KEY (company_id, job_id)
        REFERENCES jobs (company_id, job_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_employees_company_id_job_title_id FOREIGN KEY (company_id, job_title_id)
        REFERENCES job_titles (company_id, job_title_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT ck_employees_salary_nonnegative CHECK (current_salary IS NULL OR current_salary >= 0),
    CONSTRAINT ck_employees_termination_date CHECK (termination_date IS NULL OR termination_date >= hire_date)
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
