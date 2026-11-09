-- Evaluation periods belong to one company, including periods with zero participants.
-- The NOT NULL change deliberately fails if legacy rows cannot be assigned unambiguously.
ALTER TABLE evaluation_periods ADD COLUMN company_id BIGINT NULL AFTER evaluation_period_id;

UPDATE evaluation_periods p
JOIN (
    SELECT v.evaluation_period_id, MIN(e.company_id) AS company_id,
           COUNT(DISTINCT e.company_id) AS company_count
    FROM employee_evaluations v
    JOIN employees e ON e.employee_id = v.employee_id
    GROUP BY v.evaluation_period_id
) s ON s.evaluation_period_id = p.evaluation_period_id
SET p.company_id = s.company_id
WHERE s.company_count = 1;

UPDATE evaluation_periods
SET company_id = (SELECT MIN(company_id) FROM companies)
WHERE company_id IS NULL AND (SELECT COUNT(*) FROM companies) = 1;

ALTER TABLE evaluation_periods MODIFY COLUMN company_id BIGINT NOT NULL;
ALTER TABLE evaluation_periods
    ADD CONSTRAINT fk_evaluation_periods_company
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE evaluation_periods
    DROP INDEX uq_evaluation_periods_evaluation_year_evaluation_half,
    ADD UNIQUE KEY uq_evaluation_periods_company_year_half (company_id, evaluation_year, evaluation_half);
CREATE INDEX idx_evaluation_periods_company_start ON evaluation_periods (company_id, start_date);
