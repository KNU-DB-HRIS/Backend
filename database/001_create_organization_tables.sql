CREATE TABLE companies (
    company_id BIGINT NOT NULL AUTO_INCREMENT,
    company_name VARCHAR(100) NOT NULL,
    business_number VARCHAR(20) NOT NULL,
    address VARCHAR(200) NULL,
    phone VARCHAR(20) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (company_id),
    UNIQUE KEY uq_companies_business_number (business_number)
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE departments (
    department_id BIGINT NOT NULL AUTO_INCREMENT,
    company_id BIGINT NOT NULL,
    parent_department_id BIGINT NULL,
    manager_employee_id BIGINT NULL,
    department_code VARCHAR(20) NOT NULL,
    department_name VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (department_id),
    UNIQUE KEY uq_departments_company_id_department_code (company_id, department_code),
    UNIQUE KEY uq_departments_company_id_department_id (company_id, department_id),
    KEY idx_departments_company_id_parent_department_id (company_id, parent_department_id),
    KEY idx_departments_company_id_department_id_manager_employee_id (company_id, department_id, manager_employee_id),
    CONSTRAINT fk_departments_company_id FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_departments_company_id_parent_department_id FOREIGN KEY (company_id, parent_department_id)
        REFERENCES departments (company_id, department_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE positions (
    position_id BIGINT NOT NULL AUTO_INCREMENT,
    company_id BIGINT NOT NULL,
    position_code VARCHAR(20) NOT NULL,
    position_name VARCHAR(20) NOT NULL,
    position_level INT NOT NULL,
    description VARCHAR(50) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (position_id),
    UNIQUE KEY uq_positions_company_id_position_code (company_id, position_code),
    UNIQUE KEY uq_positions_company_id_position_id (company_id, position_id),
    CONSTRAINT fk_positions_company_id FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE jobs (
    job_id BIGINT NOT NULL AUTO_INCREMENT,
    company_id BIGINT NOT NULL,
    job_code VARCHAR(20) NOT NULL,
    job_name VARCHAR(100) NOT NULL,
    job_category VARCHAR(5) NOT NULL,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (job_id),
    UNIQUE KEY uq_jobs_company_id_job_code (company_id, job_code),
    UNIQUE KEY uq_jobs_company_id_job_id (company_id, job_id),
    CONSTRAINT fk_jobs_company_id FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE job_titles (
    job_title_id BIGINT NOT NULL AUTO_INCREMENT,
    company_id BIGINT NOT NULL,
    job_title_code VARCHAR(20) NOT NULL,
    job_title_name VARCHAR(50) NOT NULL,
    description VARCHAR(200) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (job_title_id),
    UNIQUE KEY uq_job_titles_company_id_job_title_code (company_id, job_title_code),
    UNIQUE KEY uq_job_titles_company_id_job_title_id (company_id, job_title_id),
    CONSTRAINT fk_job_titles_company_id FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
