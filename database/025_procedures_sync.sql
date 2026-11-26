DELIMITER $$
-- 025: 업무 프로시저를 현재 앱 규칙에 맞게 다시 만든다 (테이블, 데이터 변경 없음)
-- 009에서 만든 프로시저 중 그 뒤 마이그레이션과 어긋난 것을 고친다.
-- - sp_approve_step: 016에서 결재 상태가 PENDING → IN_PROGRESS, 단계 상태에 WAITING·SKIPPED가 생겼는데
--   프로시저는 요청 상태 'PENDING'을 요구해 어떤 결재도 처리하지 못했다. 앱(POST /approvals/{id}/approve, reject)과 같은 흐름으로 바꾼다:
--   현재 단계 PENDING → APPROVED면 다음 WAITING 단계를 PENDING으로, 없으면 요청 APPROVED / REJECTED면 남은 단계 SKIPPED, 요청 REJECTED
-- - sp_assign_employee: 퇴사자, 입사일 이전, 마지막 발령보다 앞선 적용일을 거부 (앱 EMP-06과 같은 규칙)
-- - sp_change_salary: 퇴사자, 입사일 이전, 마지막 급여 이력과 같거나 앞선 적용일을 거부 (앱 SAL-04와 같은 규칙)
-- - sp_delete_employee_without_assignment_history: 앱으로 등록한 직원은 입사(HIRE) 이력이 항상 있어 지울 수 없었다.
--   앱 EMP-08과 같이 입사 이력만 있고 다른 이력, 급여, 평가, 문서, 결재, 로그인 기록이 없을 때만 계정, 입사 이력과 함께 지운다
-- sp_set_department_manager는 바뀐 규칙이 없어 그대로 둔다.
-- 앱은 이 프로시저들을 호출하지 않는다 (같은 규칙을 API 코드로 실행). 프로시저는 DB에서 직접 업무를 처리할 때 쓰는 설계 산출물이다.


DROP PROCEDURE IF EXISTS sp_assign_employee$$

CREATE PROCEDURE sp_assign_employee(
    IN p_employee_id BIGINT,
    IN p_action_type VARCHAR(20),
    IN p_effective_date DATE,
    IN p_new_department_id BIGINT,
    IN p_new_position_id BIGINT,
    IN p_new_job_id BIGINT,
    IN p_new_job_title_id BIGINT,
    IN p_reason VARCHAR(300),
    IN p_created_by_user_id BIGINT
)
SQL SECURITY INVOKER
BEGIN
    DECLARE v_company_id BIGINT DEFAULT NULL;
    DECLARE v_department_id BIGINT;
    DECLARE v_position_id BIGINT;
    DECLARE v_job_id BIGINT;
    DECLARE v_job_title_id BIGINT;
    DECLARE v_status VARCHAR(20);
    DECLARE v_hire_date DATE;
    DECLARE v_latest DATE DEFAULT NULL;
    DECLARE v_effective_date DATE;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
      ROLLBACK;
      RESIGNAL;
    END;

    SET v_effective_date = COALESCE(p_effective_date, CURRENT_DATE());
    IF v_effective_date > CURRENT_DATE() THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Future effective dates require scheduled processing';
    END IF;
    IF p_action_type IS NULL OR p_action_type NOT IN ('TRANSFER', 'PROMOTION', 'JOB_CHANGE', 'TITLE_CHANGE', 'REASSIGNMENT')
       OR p_reason IS NULL OR TRIM(p_reason) = '' THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Action type (TRANSFER, PROMOTION, JOB_CHANGE, TITLE_CHANGE, REASSIGNMENT) and reason are required';
    END IF;
    START TRANSACTION;
    SELECT company_id, department_id, position_id, job_id, job_title_id, employment_status, hire_date
      INTO v_company_id, v_department_id, v_position_id, v_job_id, v_job_title_id, v_status, v_hire_date
      FROM employees WHERE employee_id = p_employee_id FOR UPDATE;
    IF v_company_id IS NULL THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Employee not found';
    END IF;
    IF v_status = 'TERMINATED' THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Employee is terminated';
    END IF;
    IF v_effective_date < v_hire_date THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Effective date is before hire date';
    END IF;
    SELECT MAX(COALESCE(effective_date, action_date)) INTO v_latest
      FROM assignment_history WHERE employee_id = p_employee_id;
    IF v_latest IS NOT NULL AND v_effective_date < v_latest THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Effective date is earlier than the latest assignment';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM departments
         WHERE company_id = v_company_id AND department_id = p_new_department_id AND is_active = TRUE)
       OR NOT EXISTS (SELECT 1 FROM positions
         WHERE company_id = v_company_id AND position_id = p_new_position_id AND is_active = TRUE)
       OR NOT EXISTS (SELECT 1 FROM jobs
         WHERE company_id = v_company_id AND job_id = p_new_job_id AND is_active = TRUE)
       OR (p_new_job_title_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM job_titles
         WHERE company_id = v_company_id AND job_title_id = p_new_job_title_id AND is_active = TRUE)) THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid or inactive target organization';
    END IF;
    IF v_department_id <=> p_new_department_id
       AND v_position_id <=> p_new_position_id
       AND v_job_id <=> p_new_job_id
       AND v_job_title_id <=> p_new_job_title_id THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Assignment contains no changes';
    END IF;
    IF NOT (v_department_id <=> p_new_department_id) AND EXISTS (
       SELECT 1 FROM departments WHERE manager_employee_id = p_employee_id
    ) THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Reassign current manager positions before transfer';
    END IF;

    INSERT INTO assignment_history (
      employee_id, action_type, action_date, effective_date,
      from_department_id, to_department_id,
      from_position_id, to_position_id,
      from_job_id, to_job_id,
      from_job_title_id, to_job_title_id,
      reason, created_by_user_id
    ) VALUES (
      p_employee_id, p_action_type, CURRENT_DATE(), v_effective_date,
      v_department_id, p_new_department_id,
      v_position_id, p_new_position_id,
      v_job_id, p_new_job_id,
      v_job_title_id, p_new_job_title_id,
      p_reason, p_created_by_user_id
    );
    UPDATE employees
       SET department_id = p_new_department_id,
           position_id = p_new_position_id,
           job_id = p_new_job_id,
           job_title_id = p_new_job_title_id
     WHERE employee_id = p_employee_id;
    COMMIT;
END$$

DROP PROCEDURE IF EXISTS sp_change_salary$$

CREATE PROCEDURE sp_change_salary(
    IN p_employee_id BIGINT,
    IN p_new_salary DECIMAL(15,2),
    IN p_effective_date DATE,
    IN p_reason VARCHAR(200),
    IN p_changed_by_user_id BIGINT
)
SQL SECURITY INVOKER
BEGIN
    DECLARE v_previous_salary DECIMAL(15,2) DEFAULT NULL;
    DECLARE v_employee_id BIGINT DEFAULT NULL;
    DECLARE v_status VARCHAR(20);
    DECLARE v_hire_date DATE;
    DECLARE v_latest DATE DEFAULT NULL;
    DECLARE v_effective_date DATE;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
      ROLLBACK;
      RESIGNAL;
    END;

    SET v_effective_date = COALESCE(p_effective_date, CURRENT_DATE());
    IF p_new_salary IS NULL OR p_new_salary < 0 THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'New salary must be nonnegative';
    END IF;
    IF v_effective_date > CURRENT_DATE() THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Future salary date requires scheduled processing';
    END IF;
    START TRANSACTION;
    SELECT employee_id, current_salary, employment_status, hire_date
      INTO v_employee_id, v_previous_salary, v_status, v_hire_date
      FROM employees WHERE employee_id = p_employee_id FOR UPDATE;
    IF v_employee_id IS NULL THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Employee not found';
    END IF;
    IF v_status = 'TERMINATED' THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Employee is terminated';
    END IF;
    IF v_effective_date < v_hire_date THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Effective date is before hire date';
    END IF;
    SELECT MAX(effective_date) INTO v_latest FROM salary_history WHERE employee_id = p_employee_id;
    IF v_latest IS NOT NULL AND v_effective_date <= v_latest THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Effective date must be after the latest salary change';
    END IF;
    IF v_previous_salary <=> p_new_salary THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'New salary equals current salary';
    END IF;
    INSERT INTO salary_history (
      employee_id, previous_salary, new_salary, effective_date, reason, changed_by_user_id
    ) VALUES (p_employee_id, v_previous_salary, p_new_salary, v_effective_date, p_reason, p_changed_by_user_id);
    UPDATE employees SET current_salary = p_new_salary WHERE employee_id = p_employee_id;
    COMMIT;
END$$

DROP PROCEDURE IF EXISTS sp_approve_step$$

CREATE PROCEDURE sp_approve_step(
    IN p_approval_request_id BIGINT,
    IN p_step_order INT,
    IN p_approver_user_id BIGINT,
    IN p_decision VARCHAR(20),
    IN p_comments VARCHAR(500)
)
SQL SECURITY INVOKER
BEGIN
    DECLARE v_request_status VARCHAR(20) DEFAULT NULL;
    DECLARE v_step_status VARCHAR(20) DEFAULT NULL;
    DECLARE v_expected_approver_user_id BIGINT DEFAULT NULL;
    DECLARE v_prior_unapproved INT DEFAULT 0;
    DECLARE v_next_step INT DEFAULT NULL;
    DECLARE v_decision VARCHAR(20);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
      ROLLBACK;
      RESIGNAL;
    END;
    SET v_decision = UPPER(p_decision);
    IF v_decision IS NULL OR v_decision NOT IN ('APPROVED', 'REJECTED') THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Decision must be APPROVED or REJECTED';
    END IF;
    START TRANSACTION;
    SELECT status INTO v_request_status FROM approval_requests
      WHERE approval_request_id = p_approval_request_id FOR UPDATE;
    IF v_request_status IS NULL OR v_request_status <> 'IN_PROGRESS' THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Approval request is not in progress';
    END IF;
    SELECT status, approver_user_id INTO v_step_status, v_expected_approver_user_id
      FROM approval_steps
      WHERE approval_request_id = p_approval_request_id AND step_order = p_step_order FOR UPDATE;
    IF v_step_status IS NULL OR v_step_status <> 'PENDING'
       OR p_approver_user_id IS NULL
       OR v_expected_approver_user_id <> p_approver_user_id THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Step not pending or approver mismatch';
    END IF;
    SELECT COUNT(*) INTO v_prior_unapproved FROM approval_steps
      WHERE approval_request_id = p_approval_request_id AND step_order < p_step_order
        AND status <> 'APPROVED';
    IF v_prior_unapproved > 0 THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Previous approval step is incomplete';
    END IF;
    UPDATE approval_steps
       SET status = v_decision, comments = p_comments, decided_at = CURRENT_TIMESTAMP(6)
     WHERE approval_request_id = p_approval_request_id AND step_order = p_step_order;
    IF v_decision = 'REJECTED' THEN
       UPDATE approval_steps SET status = 'SKIPPED'
        WHERE approval_request_id = p_approval_request_id AND status IN ('WAITING', 'PENDING');
       UPDATE approval_requests
          SET status = 'REJECTED', completed_at = CURRENT_TIMESTAMP(6)
        WHERE approval_request_id = p_approval_request_id;
    ELSE
       SELECT MIN(step_order) INTO v_next_step FROM approval_steps
        WHERE approval_request_id = p_approval_request_id AND status = 'WAITING';
       IF v_next_step IS NOT NULL THEN
          UPDATE approval_steps SET status = 'PENDING'
           WHERE approval_request_id = p_approval_request_id AND step_order = v_next_step;
       ELSE
          UPDATE approval_requests
             SET status = 'APPROVED', completed_at = CURRENT_TIMESTAMP(6)
           WHERE approval_request_id = p_approval_request_id;
       END IF;
    END IF;
    COMMIT;
END$$

DROP PROCEDURE IF EXISTS sp_delete_employee_without_assignment_history$$

CREATE PROCEDURE sp_delete_employee_without_assignment_history(IN p_employee_id BIGINT)
SQL SECURITY INVOKER
BEGIN
    DECLARE v_employee_id BIGINT DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
      ROLLBACK;
      RESIGNAL;
    END;
    START TRANSACTION;
    SELECT employee_id INTO v_employee_id FROM employees
      WHERE employee_id = p_employee_id FOR UPDATE;
    IF v_employee_id IS NULL THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Employee not found';
    END IF;
    IF EXISTS (SELECT 1 FROM departments WHERE manager_employee_id = p_employee_id) THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Reassign department manager before delete';
    END IF;
    IF EXISTS (SELECT 1 FROM assignment_history WHERE employee_id = p_employee_id AND action_type <> 'HIRE')
       OR EXISTS (SELECT 1 FROM salary_history WHERE employee_id = p_employee_id)
       OR EXISTS (SELECT 1 FROM employee_evaluations
                  WHERE employee_id = p_employee_id OR evaluator_employee_id = p_employee_id)
       OR EXISTS (SELECT 1 FROM evaluation_stage_records WHERE evaluator_id = p_employee_id)
       OR EXISTS (SELECT 1 FROM documents WHERE employee_id = p_employee_id)
       OR EXISTS (SELECT 1 FROM payroll_statements WHERE employee_id = p_employee_id)
       OR EXISTS (SELECT 1 FROM attendance_records WHERE employee_id = p_employee_id)
       OR EXISTS (SELECT 1 FROM users WHERE employee_id = p_employee_id AND last_login_at IS NOT NULL)
       OR EXISTS (SELECT 1 FROM approval_requests r JOIN users u ON u.user_id = r.requester_user_id
                  WHERE u.employee_id = p_employee_id)
       OR EXISTS (SELECT 1 FROM approval_steps s JOIN users u ON u.user_id = s.approver_user_id
                  WHERE u.employee_id = p_employee_id) THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot delete employee with history';
    END IF;
    DELETE ur FROM user_roles ur JOIN users u ON u.user_id = ur.user_id WHERE u.employee_id = p_employee_id;
    DELETE FROM users WHERE employee_id = p_employee_id;
    DELETE FROM assignment_history WHERE employee_id = p_employee_id;
    DELETE FROM employees WHERE employee_id = p_employee_id;
    COMMIT;
END$$

DELIMITER ;
