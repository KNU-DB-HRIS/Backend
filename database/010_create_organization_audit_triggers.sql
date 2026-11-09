DELIMITER $$

CREATE TRIGGER trg_departments_before_insert BEFORE INSERT ON departments
FOR EACH ROW
BEGIN
    IF NEW.parent_department_id = NEW.department_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Department cannot be its own parent';
    END IF;
END$$

CREATE TRIGGER trg_departments_before_update BEFORE UPDATE ON departments
FOR EACH ROW
BEGIN
    IF NEW.parent_department_id = NEW.department_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Department cannot be its own parent';
    END IF;
END$$

CREATE TRIGGER trg_companies_after_insert AFTER INSERT ON companies
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'companies', NEW.company_id,
        NULL, JSON_OBJECT(
            'company_id', NEW.company_id,
            'company_name', NEW.company_name,
            'business_number', NEW.business_number,
            'address', NEW.address,
            'phone', NEW.phone,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_companies_after_update AFTER UPDATE ON companies
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'companies', NEW.company_id,
        JSON_OBJECT(
            'company_id', OLD.company_id,
            'company_name', OLD.company_name,
            'business_number', OLD.business_number,
            'address', OLD.address,
            'phone', OLD.phone,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'company_id', NEW.company_id,
            'company_name', NEW.company_name,
            'business_number', NEW.business_number,
            'address', NEW.address,
            'phone', NEW.phone,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_companies_after_delete AFTER DELETE ON companies
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'companies', OLD.company_id,
        JSON_OBJECT(
            'company_id', OLD.company_id,
            'company_name', OLD.company_name,
            'business_number', OLD.business_number,
            'address', OLD.address,
            'phone', OLD.phone,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_departments_after_insert AFTER INSERT ON departments
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'departments', NEW.department_id,
        NULL, JSON_OBJECT(
            'department_id', NEW.department_id,
            'company_id', NEW.company_id,
            'parent_department_id', NEW.parent_department_id,
            'manager_employee_id', NEW.manager_employee_id,
            'department_code', NEW.department_code,
            'department_name', NEW.department_name,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_departments_after_update AFTER UPDATE ON departments
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'departments', NEW.department_id,
        JSON_OBJECT(
            'department_id', OLD.department_id,
            'company_id', OLD.company_id,
            'parent_department_id', OLD.parent_department_id,
            'manager_employee_id', OLD.manager_employee_id,
            'department_code', OLD.department_code,
            'department_name', OLD.department_name,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'department_id', NEW.department_id,
            'company_id', NEW.company_id,
            'parent_department_id', NEW.parent_department_id,
            'manager_employee_id', NEW.manager_employee_id,
            'department_code', NEW.department_code,
            'department_name', NEW.department_name,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_departments_after_delete AFTER DELETE ON departments
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'departments', OLD.department_id,
        JSON_OBJECT(
            'department_id', OLD.department_id,
            'company_id', OLD.company_id,
            'parent_department_id', OLD.parent_department_id,
            'manager_employee_id', OLD.manager_employee_id,
            'department_code', OLD.department_code,
            'department_name', OLD.department_name,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_positions_after_insert AFTER INSERT ON positions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'positions', NEW.position_id,
        NULL, JSON_OBJECT(
            'position_id', NEW.position_id,
            'company_id', NEW.company_id,
            'position_code', NEW.position_code,
            'position_name', NEW.position_name,
            'position_level', NEW.position_level,
            'description', NEW.description,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_positions_after_update AFTER UPDATE ON positions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'positions', NEW.position_id,
        JSON_OBJECT(
            'position_id', OLD.position_id,
            'company_id', OLD.company_id,
            'position_code', OLD.position_code,
            'position_name', OLD.position_name,
            'position_level', OLD.position_level,
            'description', OLD.description,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'position_id', NEW.position_id,
            'company_id', NEW.company_id,
            'position_code', NEW.position_code,
            'position_name', NEW.position_name,
            'position_level', NEW.position_level,
            'description', NEW.description,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_positions_after_delete AFTER DELETE ON positions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'positions', OLD.position_id,
        JSON_OBJECT(
            'position_id', OLD.position_id,
            'company_id', OLD.company_id,
            'position_code', OLD.position_code,
            'position_name', OLD.position_name,
            'position_level', OLD.position_level,
            'description', OLD.description,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_jobs_after_insert AFTER INSERT ON jobs
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'jobs', NEW.job_id,
        NULL, JSON_OBJECT(
            'job_id', NEW.job_id,
            'company_id', NEW.company_id,
            'job_code', NEW.job_code,
            'job_name', NEW.job_name,
            'job_category', NEW.job_category,
            'description', NEW.description,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_jobs_after_update AFTER UPDATE ON jobs
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'jobs', NEW.job_id,
        JSON_OBJECT(
            'job_id', OLD.job_id,
            'company_id', OLD.company_id,
            'job_code', OLD.job_code,
            'job_name', OLD.job_name,
            'job_category', OLD.job_category,
            'description', OLD.description,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'job_id', NEW.job_id,
            'company_id', NEW.company_id,
            'job_code', NEW.job_code,
            'job_name', NEW.job_name,
            'job_category', NEW.job_category,
            'description', NEW.description,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_jobs_after_delete AFTER DELETE ON jobs
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'jobs', OLD.job_id,
        JSON_OBJECT(
            'job_id', OLD.job_id,
            'company_id', OLD.company_id,
            'job_code', OLD.job_code,
            'job_name', OLD.job_name,
            'job_category', OLD.job_category,
            'description', OLD.description,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_job_titles_after_insert AFTER INSERT ON job_titles
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'job_titles', NEW.job_title_id,
        NULL, JSON_OBJECT(
            'job_title_id', NEW.job_title_id,
            'company_id', NEW.company_id,
            'job_title_code', NEW.job_title_code,
            'job_title_name', NEW.job_title_name,
            'description', NEW.description,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_job_titles_after_update AFTER UPDATE ON job_titles
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'job_titles', NEW.job_title_id,
        JSON_OBJECT(
            'job_title_id', OLD.job_title_id,
            'company_id', OLD.company_id,
            'job_title_code', OLD.job_title_code,
            'job_title_name', OLD.job_title_name,
            'description', OLD.description,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'job_title_id', NEW.job_title_id,
            'company_id', NEW.company_id,
            'job_title_code', NEW.job_title_code,
            'job_title_name', NEW.job_title_name,
            'description', NEW.description,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_job_titles_after_delete AFTER DELETE ON job_titles
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'job_titles', OLD.job_title_id,
        JSON_OBJECT(
            'job_title_id', OLD.job_title_id,
            'company_id', OLD.company_id,
            'job_title_code', OLD.job_title_code,
            'job_title_name', OLD.job_title_name,
            'description', OLD.description,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

DELIMITER ;
