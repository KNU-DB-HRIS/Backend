CREATE TABLE evaluation_periods (
    evaluation_period_id BIGINT NOT NULL AUTO_INCREMENT,
    evaluation_year INT NOT NULL,
    evaluation_half VARCHAR(2) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (evaluation_period_id),
    UNIQUE KEY uq_evaluation_periods_evaluation_year_evaluation_half (evaluation_year, evaluation_half),
    CONSTRAINT ck_evaluation_periods_dates CHECK (end_date >= start_date),
    CONSTRAINT ck_evaluation_periods_half CHECK (evaluation_half IN ('H1', 'H2'))
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE employee_evaluations (
    employee_evaluation_id BIGINT NOT NULL AUTO_INCREMENT,
    employee_id BIGINT NOT NULL,
    evaluator_employee_id BIGINT NOT NULL,
    evaluation_period_id BIGINT NOT NULL,
    score DECIMAL(5,2) NULL,
    grade VARCHAR(10) NULL,
    comments VARCHAR(500) NULL,
    status VARCHAR(20) NOT NULL,
    evaluated_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (employee_evaluation_id),
    UNIQUE KEY uq_employee_evaluations_employee_id_evaluation_period_id (employee_id, evaluation_period_id),
    KEY idx_employee_evaluations_evaluation_period_id_status (evaluation_period_id, status),
    KEY idx_employee_evaluations_evaluator_employee_id (evaluator_employee_id),
    CONSTRAINT fk_employee_evaluations_employee_id FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_employee_evaluations_evaluator_employee_id FOREIGN KEY (evaluator_employee_id) REFERENCES employees (employee_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_employee_evaluations_evaluation_period_id FOREIGN KEY (evaluation_period_id) REFERENCES evaluation_periods (evaluation_period_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT ck_employee_evaluations_score CHECK (score IS NULL OR score >= 0)
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
