DELIMITER $$

CREATE PROCEDURE sp_set_department_manager(
    IN p_department_id BIGINT,
    IN p_manager_employee_id BIGINT
)
SQL SECURITY INVOKER
BEGIN
    DECLARE v_company_id BIGINT DEFAULT NULL;
    DECLARE v_manager_company_id BIGINT DEFAULT NULL;
    DECLARE v_manager_department_id BIGINT DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
      ROLLBACK;
      RESIGNAL;
    END;

    START TRANSACTION;
    SELECT company_id INTO v_company_id
      FROM departments WHERE department_id = p_department_id FOR UPDATE;
    IF v_company_id IS NULL THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Department not found';
    END IF;
    IF p_manager_employee_id IS NOT NULL THEN
      SELECT company_id, department_id
        INTO v_manager_company_id, v_manager_department_id
        FROM employees WHERE employee_id = p_manager_employee_id FOR UPDATE;
      IF v_manager_company_id IS NULL
         OR v_manager_company_id <> v_company_id
         OR v_manager_department_id <> p_department_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Manager must work in same department/company';
      END IF;
    END IF;
    UPDATE departments SET manager_employee_id = p_manager_employee_id
      WHERE department_id = p_department_id;
    COMMIT;
END$$

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
    IF p_action_type IS NULL OR TRIM(p_action_type) = ''
       OR p_reason IS NULL OR TRIM(p_reason) = '' THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Action type and reason are required';
    END IF;
    START TRANSACTION;
    SELECT company_id, department_id, position_id, job_id, job_title_id
      INTO v_company_id, v_department_id, v_position_id, v_job_id, v_job_title_id
      FROM employees WHERE employee_id = p_employee_id FOR UPDATE;
    IF v_company_id IS NULL THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Employee not found';
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
    SELECT employee_id, current_salary INTO v_employee_id, v_previous_salary
      FROM employees WHERE employee_id = p_employee_id FOR UPDATE;
    IF v_employee_id IS NULL THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Employee not found';
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
    DECLARE v_remaining_steps INT DEFAULT 0;
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
    IF v_request_status IS NULL OR v_request_status <> 'PENDING' THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Approval request not pending';
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
       UPDATE approval_requests
          SET status = 'REJECTED', completed_at = CURRENT_TIMESTAMP(6)
        WHERE approval_request_id = p_approval_request_id;
    ELSE
       SELECT COUNT(*) INTO v_remaining_steps FROM approval_steps
         WHERE approval_request_id = p_approval_request_id AND status <> 'APPROVED';
       IF v_remaining_steps = 0 THEN
          UPDATE approval_requests
             SET status = 'APPROVED', completed_at = CURRENT_TIMESTAMP(6)
           WHERE approval_request_id = p_approval_request_id;
       END IF;
    END IF;
    COMMIT;
END$$

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
    IF EXISTS (SELECT 1 FROM assignment_history WHERE employee_id = p_employee_id) THEN
       SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot delete employee with assignment history';
    END IF;
    DELETE FROM employees WHERE employee_id = p_employee_id;
    COMMIT;
END$$

DELIMITER ;
