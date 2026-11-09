DELIMITER $$

CREATE TRIGGER trg_employees_after_insert AFTER INSERT ON employees
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'employees', NEW.employee_id,
        NULL, JSON_OBJECT(
            'employee_id', NEW.employee_id,
            'company_id', NEW.company_id,
            'employee_no', NEW.employee_no,
            'employee_name', NEW.employee_name,
            'birth_date', NEW.birth_date,
            'gender', NEW.gender,
            'phone', NEW.phone,
            'email', NEW.email,
            'hire_date', NEW.hire_date,
            'termination_date', NEW.termination_date,
            'employment_type', NEW.employment_type,
            'employment_status', NEW.employment_status,
            'department_id', NEW.department_id,
            'position_id', NEW.position_id,
            'job_id', NEW.job_id,
            'job_title_id', NEW.job_title_id,
            'current_salary', NEW.current_salary,
            'profile_image_url', NEW.profile_image_url,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_employees_after_update AFTER UPDATE ON employees
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'employees', NEW.employee_id,
        JSON_OBJECT(
            'employee_id', OLD.employee_id,
            'company_id', OLD.company_id,
            'employee_no', OLD.employee_no,
            'employee_name', OLD.employee_name,
            'birth_date', OLD.birth_date,
            'gender', OLD.gender,
            'phone', OLD.phone,
            'email', OLD.email,
            'hire_date', OLD.hire_date,
            'termination_date', OLD.termination_date,
            'employment_type', OLD.employment_type,
            'employment_status', OLD.employment_status,
            'department_id', OLD.department_id,
            'position_id', OLD.position_id,
            'job_id', OLD.job_id,
            'job_title_id', OLD.job_title_id,
            'current_salary', OLD.current_salary,
            'profile_image_url', OLD.profile_image_url,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'employee_id', NEW.employee_id,
            'company_id', NEW.company_id,
            'employee_no', NEW.employee_no,
            'employee_name', NEW.employee_name,
            'birth_date', NEW.birth_date,
            'gender', NEW.gender,
            'phone', NEW.phone,
            'email', NEW.email,
            'hire_date', NEW.hire_date,
            'termination_date', NEW.termination_date,
            'employment_type', NEW.employment_type,
            'employment_status', NEW.employment_status,
            'department_id', NEW.department_id,
            'position_id', NEW.position_id,
            'job_id', NEW.job_id,
            'job_title_id', NEW.job_title_id,
            'current_salary', NEW.current_salary,
            'profile_image_url', NEW.profile_image_url,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_employees_after_delete AFTER DELETE ON employees
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'employees', OLD.employee_id,
        JSON_OBJECT(
            'employee_id', OLD.employee_id,
            'company_id', OLD.company_id,
            'employee_no', OLD.employee_no,
            'employee_name', OLD.employee_name,
            'birth_date', OLD.birth_date,
            'gender', OLD.gender,
            'phone', OLD.phone,
            'email', OLD.email,
            'hire_date', OLD.hire_date,
            'termination_date', OLD.termination_date,
            'employment_type', OLD.employment_type,
            'employment_status', OLD.employment_status,
            'department_id', OLD.department_id,
            'position_id', OLD.position_id,
            'job_id', OLD.job_id,
            'job_title_id', OLD.job_title_id,
            'current_salary', OLD.current_salary,
            'profile_image_url', OLD.profile_image_url,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_assignment_history_after_insert AFTER INSERT ON assignment_history
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'assignment_history', NEW.assignment_history_id,
        NULL, JSON_OBJECT(
            'assignment_history_id', NEW.assignment_history_id,
            'employee_id', NEW.employee_id,
            'action_type', NEW.action_type,
            'action_date', NEW.action_date,
            'effective_date', NEW.effective_date,
            'from_department_id', NEW.from_department_id,
            'to_department_id', NEW.to_department_id,
            'from_position_id', NEW.from_position_id,
            'to_position_id', NEW.to_position_id,
            'from_job_id', NEW.from_job_id,
            'to_job_id', NEW.to_job_id,
            'from_job_title_id', NEW.from_job_title_id,
            'to_job_title_id', NEW.to_job_title_id,
            'reason', NEW.reason,
            'document_url', NEW.document_url,
            'created_by_user_id', NEW.created_by_user_id,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_assignment_history_after_update AFTER UPDATE ON assignment_history
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'assignment_history', NEW.assignment_history_id,
        JSON_OBJECT(
            'assignment_history_id', OLD.assignment_history_id,
            'employee_id', OLD.employee_id,
            'action_type', OLD.action_type,
            'action_date', OLD.action_date,
            'effective_date', OLD.effective_date,
            'from_department_id', OLD.from_department_id,
            'to_department_id', OLD.to_department_id,
            'from_position_id', OLD.from_position_id,
            'to_position_id', OLD.to_position_id,
            'from_job_id', OLD.from_job_id,
            'to_job_id', OLD.to_job_id,
            'from_job_title_id', OLD.from_job_title_id,
            'to_job_title_id', OLD.to_job_title_id,
            'reason', OLD.reason,
            'document_url', OLD.document_url,
            'created_by_user_id', OLD.created_by_user_id,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'assignment_history_id', NEW.assignment_history_id,
            'employee_id', NEW.employee_id,
            'action_type', NEW.action_type,
            'action_date', NEW.action_date,
            'effective_date', NEW.effective_date,
            'from_department_id', NEW.from_department_id,
            'to_department_id', NEW.to_department_id,
            'from_position_id', NEW.from_position_id,
            'to_position_id', NEW.to_position_id,
            'from_job_id', NEW.from_job_id,
            'to_job_id', NEW.to_job_id,
            'from_job_title_id', NEW.from_job_title_id,
            'to_job_title_id', NEW.to_job_title_id,
            'reason', NEW.reason,
            'document_url', NEW.document_url,
            'created_by_user_id', NEW.created_by_user_id,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_assignment_history_after_delete AFTER DELETE ON assignment_history
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'assignment_history', OLD.assignment_history_id,
        JSON_OBJECT(
            'assignment_history_id', OLD.assignment_history_id,
            'employee_id', OLD.employee_id,
            'action_type', OLD.action_type,
            'action_date', OLD.action_date,
            'effective_date', OLD.effective_date,
            'from_department_id', OLD.from_department_id,
            'to_department_id', OLD.to_department_id,
            'from_position_id', OLD.from_position_id,
            'to_position_id', OLD.to_position_id,
            'from_job_id', OLD.from_job_id,
            'to_job_id', OLD.to_job_id,
            'from_job_title_id', OLD.from_job_title_id,
            'to_job_title_id', OLD.to_job_title_id,
            'reason', OLD.reason,
            'document_url', OLD.document_url,
            'created_by_user_id', OLD.created_by_user_id,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_salary_history_after_insert AFTER INSERT ON salary_history
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'salary_history', NEW.salary_history_id,
        NULL, JSON_OBJECT(
            'salary_history_id', NEW.salary_history_id,
            'employee_id', NEW.employee_id,
            'previous_salary', NEW.previous_salary,
            'new_salary', NEW.new_salary,
            'effective_date', NEW.effective_date,
            'reason', NEW.reason,
            'changed_by_user_id', NEW.changed_by_user_id,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_salary_history_after_update AFTER UPDATE ON salary_history
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'salary_history', NEW.salary_history_id,
        JSON_OBJECT(
            'salary_history_id', OLD.salary_history_id,
            'employee_id', OLD.employee_id,
            'previous_salary', OLD.previous_salary,
            'new_salary', OLD.new_salary,
            'effective_date', OLD.effective_date,
            'reason', OLD.reason,
            'changed_by_user_id', OLD.changed_by_user_id,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'salary_history_id', NEW.salary_history_id,
            'employee_id', NEW.employee_id,
            'previous_salary', NEW.previous_salary,
            'new_salary', NEW.new_salary,
            'effective_date', NEW.effective_date,
            'reason', NEW.reason,
            'changed_by_user_id', NEW.changed_by_user_id,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_salary_history_after_delete AFTER DELETE ON salary_history
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'salary_history', OLD.salary_history_id,
        JSON_OBJECT(
            'salary_history_id', OLD.salary_history_id,
            'employee_id', OLD.employee_id,
            'previous_salary', OLD.previous_salary,
            'new_salary', OLD.new_salary,
            'effective_date', OLD.effective_date,
            'reason', OLD.reason,
            'changed_by_user_id', OLD.changed_by_user_id,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

DELIMITER ;
