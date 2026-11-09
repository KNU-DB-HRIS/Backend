CREATE TABLE attendance_records (
  attendance_id  BIGINT AUTO_INCREMENT PRIMARY KEY,
  employee_id    BIGINT      NOT NULL,
  work_date      DATE        NOT NULL,
  status         VARCHAR(20) NOT NULL,
  check_in_at    DATETIME,
  created_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_att_day UNIQUE (employee_id, work_date),
  CONSTRAINT ck_att_status CHECK (status IN ('PRESENT','LEAVE','ABSENT')),
  CONSTRAINT fk_att_employee FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);




ALTER TABLE salary_history
  ADD COLUMN base_salary        INT NULL,
  ADD COLUMN position_allowance INT NULL,
  ADD COLUMN meal_allowance     INT NULL,
  ADD COLUMN other_allowance    INT NULL,
  ADD COLUMN components_status  VARCHAR(10) NOT NULL DEFAULT 'UNKNOWN';
ALTER TABLE salary_history ADD CONSTRAINT ck_salary_components CHECK (
  (components_status = 'UNKNOWN' AND base_salary IS NULL AND position_allowance IS NULL
     AND meal_allowance IS NULL AND other_allowance IS NULL)
  OR (components_status = 'COMPLETE' AND base_salary IS NOT NULL AND position_allowance IS NOT NULL
     AND meal_allowance IS NOT NULL AND other_allowance IS NOT NULL
     AND base_salary + position_allowance + meal_allowance + other_allowance = new_salary)
);



CREATE TABLE evaluation_stage_records (
  stage_record_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  evaluation_id   BIGINT       NOT NULL,
  stage           VARCHAR(10)  NOT NULL,
  evaluator_id    BIGINT       NOT NULL,
  score           DECIMAL(5,2),
  comment         VARCHAR(500),
  submitted_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_stage_once UNIQUE (evaluation_id, stage, evaluator_id),
  CONSTRAINT ck_stage CHECK (stage IN ('GOAL','SELF','PEER','LEADER')),
  CONSTRAINT ck_score CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
  CONSTRAINT fk_esr_eval FOREIGN KEY (evaluation_id) REFERENCES employee_evaluations(employee_evaluation_id),
  CONSTRAINT fk_esr_evaluator FOREIGN KEY (evaluator_id) REFERENCES employees(employee_id)
);


ALTER TABLE companies
  ADD COLUMN ceo_name     VARCHAR(50),
  ADD COLUMN founded_date DATE,
  ADD COLUMN email        VARCHAR(100),
  ADD COLUMN homepage     VARCHAR(200),
  ADD COLUMN industry     VARCHAR(50),
  ADD COLUMN logo_url     VARCHAR(500);


ALTER TABLE departments ADD COLUMN description VARCHAR(200);
ALTER TABLE positions   ADD COLUMN min_tenure_months INT;

ALTER TABLE jobs ADD COLUMN job_family VARCHAR(20);
ALTER TABLE jobs MODIFY COLUMN job_category VARCHAR(30) NOT NULL;

ALTER TABLE companies ADD COLUMN name_en VARCHAR(100);


ALTER TABLE employees
  ADD COLUMN address   VARCHAR(200),
  ADD COLUMN education VARCHAR(50);



CREATE TABLE hr_events (
  event_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
  company_id  BIGINT       NOT NULL,
  title       VARCHAR(100) NOT NULL,
  start_at    DATETIME     NOT NULL,
  end_at      DATETIME,
  all_day     BOOLEAN      NOT NULL DEFAULT FALSE,
  location    VARCHAR(100),
  target      VARCHAR(100),
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_ev_company FOREIGN KEY (company_id) REFERENCES companies(company_id)
);



CREATE TABLE payroll_statements (
  statement_id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  employee_id          BIGINT      NOT NULL,
  pay_month            CHAR(7)     NOT NULL,
  base_salary          INT         NOT NULL,
  position_allowance   INT         NOT NULL,
  meal_allowance       INT         NOT NULL,
  other_allowance      INT         NOT NULL,
  gross_pay            INT         NOT NULL,
  national_pension     INT         NOT NULL,
  health_insurance     INT         NOT NULL,
  long_term_care       INT         NOT NULL,
  employment_insurance INT         NOT NULL,
  income_tax           INT         NOT NULL,
  local_income_tax     INT         NOT NULL,
  total_deduction      INT         NOT NULL,
  net_pay              INT         NOT NULL,
  paid_at              DATE,
  status               VARCHAR(10) NOT NULL DEFAULT 'DRAFT',
  created_at           DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_ps_month  UNIQUE (employee_id, pay_month),
  CONSTRAINT ck_ps_gross  CHECK (gross_pay = base_salary + position_allowance + meal_allowance + other_allowance),
  CONSTRAINT ck_ps_ded    CHECK (total_deduction = national_pension + health_insurance + long_term_care + employment_insurance + income_tax + local_income_tax),
  CONSTRAINT ck_ps_net    CHECK (net_pay = gross_pay - total_deduction),
  CONSTRAINT ck_ps_status CHECK (status IN ('DRAFT','CONFIRMED','PAID')),
  CONSTRAINT ck_ps_paid   CHECK (status <> 'PAID' OR paid_at IS NOT NULL),
  CONSTRAINT fk_ps_employee FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);
