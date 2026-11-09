DELIMITER $$

CREATE TRIGGER trg_users_after_insert AFTER INSERT ON users
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'users', NEW.user_id,
        NULL, JSON_OBJECT(
            'user_id', NEW.user_id,
            'employee_id', NEW.employee_id,
            'username', NEW.username,
            'status', NEW.status,
            'last_login_at', NEW.last_login_at,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_users_after_update AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'users', NEW.user_id,
        JSON_OBJECT(
            'user_id', OLD.user_id,
            'employee_id', OLD.employee_id,
            'username', OLD.username,
            'status', OLD.status,
            'last_login_at', OLD.last_login_at,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'user_id', NEW.user_id,
            'employee_id', NEW.employee_id,
            'username', NEW.username,
            'status', NEW.status,
            'last_login_at', NEW.last_login_at,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_users_after_delete AFTER DELETE ON users
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        IF(@hris_actor_user_id = OLD.user_id, NULL, @hris_actor_user_id), 'DELETE', 'users', OLD.user_id,
        JSON_OBJECT(
            'user_id', OLD.user_id,
            'employee_id', OLD.employee_id,
            'username', OLD.username,
            'status', OLD.status,
            'last_login_at', OLD.last_login_at,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_roles_after_insert AFTER INSERT ON roles
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'roles', NEW.role_id,
        NULL, JSON_OBJECT(
            'role_id', NEW.role_id,
            'role_code', NEW.role_code,
            'role_name', NEW.role_name,
            'description', NEW.description,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_roles_after_update AFTER UPDATE ON roles
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'roles', NEW.role_id,
        JSON_OBJECT(
            'role_id', OLD.role_id,
            'role_code', OLD.role_code,
            'role_name', OLD.role_name,
            'description', OLD.description,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'role_id', NEW.role_id,
            'role_code', NEW.role_code,
            'role_name', NEW.role_name,
            'description', NEW.description,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_roles_after_delete AFTER DELETE ON roles
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'roles', OLD.role_id,
        JSON_OBJECT(
            'role_id', OLD.role_id,
            'role_code', OLD.role_code,
            'role_name', OLD.role_name,
            'description', OLD.description,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_permissions_after_insert AFTER INSERT ON permissions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'permissions', NEW.permission_id,
        NULL, JSON_OBJECT(
            'permission_id', NEW.permission_id,
            'permission_code', NEW.permission_code,
            'permission_name', NEW.permission_name,
            'resource_type', NEW.resource_type,
            'action_type', NEW.action_type,
            'description', NEW.description,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_permissions_after_update AFTER UPDATE ON permissions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'permissions', NEW.permission_id,
        JSON_OBJECT(
            'permission_id', OLD.permission_id,
            'permission_code', OLD.permission_code,
            'permission_name', OLD.permission_name,
            'resource_type', OLD.resource_type,
            'action_type', OLD.action_type,
            'description', OLD.description,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'permission_id', NEW.permission_id,
            'permission_code', NEW.permission_code,
            'permission_name', NEW.permission_name,
            'resource_type', NEW.resource_type,
            'action_type', NEW.action_type,
            'description', NEW.description,
            'is_active', NEW.is_active,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_permissions_after_delete AFTER DELETE ON permissions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'permissions', OLD.permission_id,
        JSON_OBJECT(
            'permission_id', OLD.permission_id,
            'permission_code', OLD.permission_code,
            'permission_name', OLD.permission_name,
            'resource_type', OLD.resource_type,
            'action_type', OLD.action_type,
            'description', OLD.description,
            'is_active', OLD.is_active,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_user_roles_after_insert AFTER INSERT ON user_roles
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'user_roles', NULL,
        NULL, JSON_OBJECT(
            'user_id', NEW.user_id,
            'role_id', NEW.role_id,
            'created_at', NEW.created_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_user_roles_after_update AFTER UPDATE ON user_roles
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'user_roles', NULL,
        JSON_OBJECT(
            'user_id', OLD.user_id,
            'role_id', OLD.role_id,
            'created_at', OLD.created_at
        ), JSON_OBJECT(
            'user_id', NEW.user_id,
            'role_id', NEW.role_id,
            'created_at', NEW.created_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_user_roles_after_delete AFTER DELETE ON user_roles
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'user_roles', NULL,
        JSON_OBJECT(
            'user_id', OLD.user_id,
            'role_id', OLD.role_id,
            'created_at', OLD.created_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_role_permissions_after_insert AFTER INSERT ON role_permissions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'role_permissions', NULL,
        NULL, JSON_OBJECT(
            'role_id', NEW.role_id,
            'permission_id', NEW.permission_id,
            'created_at', NEW.created_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_role_permissions_after_update AFTER UPDATE ON role_permissions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'role_permissions', NULL,
        JSON_OBJECT(
            'role_id', OLD.role_id,
            'permission_id', OLD.permission_id,
            'created_at', OLD.created_at
        ), JSON_OBJECT(
            'role_id', NEW.role_id,
            'permission_id', NEW.permission_id,
            'created_at', NEW.created_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_role_permissions_after_delete AFTER DELETE ON role_permissions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'role_permissions', NULL,
        JSON_OBJECT(
            'role_id', OLD.role_id,
            'permission_id', OLD.permission_id,
            'created_at', OLD.created_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

DELIMITER ;
