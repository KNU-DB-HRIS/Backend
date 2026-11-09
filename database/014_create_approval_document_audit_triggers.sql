DELIMITER $$

CREATE TRIGGER trg_approval_requests_after_insert AFTER INSERT ON approval_requests
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'approval_requests', NEW.approval_request_id,
        NULL, JSON_OBJECT(
            'approval_request_id', NEW.approval_request_id,
            'request_type', NEW.request_type,
            'reference_id', NEW.reference_id,
            'requester_user_id', NEW.requester_user_id,
            'title', NEW.title,
            'content', NEW.content,
            'status', NEW.status,
            'requested_at', NEW.requested_at,
            'completed_at', NEW.completed_at,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_approval_requests_after_update AFTER UPDATE ON approval_requests
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'approval_requests', NEW.approval_request_id,
        JSON_OBJECT(
            'approval_request_id', OLD.approval_request_id,
            'request_type', OLD.request_type,
            'reference_id', OLD.reference_id,
            'requester_user_id', OLD.requester_user_id,
            'title', OLD.title,
            'content', OLD.content,
            'status', OLD.status,
            'requested_at', OLD.requested_at,
            'completed_at', OLD.completed_at,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'approval_request_id', NEW.approval_request_id,
            'request_type', NEW.request_type,
            'reference_id', NEW.reference_id,
            'requester_user_id', NEW.requester_user_id,
            'title', NEW.title,
            'content', NEW.content,
            'status', NEW.status,
            'requested_at', NEW.requested_at,
            'completed_at', NEW.completed_at,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_approval_requests_after_delete AFTER DELETE ON approval_requests
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'approval_requests', OLD.approval_request_id,
        JSON_OBJECT(
            'approval_request_id', OLD.approval_request_id,
            'request_type', OLD.request_type,
            'reference_id', OLD.reference_id,
            'requester_user_id', OLD.requester_user_id,
            'title', OLD.title,
            'content', OLD.content,
            'status', OLD.status,
            'requested_at', OLD.requested_at,
            'completed_at', OLD.completed_at,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_approval_steps_after_insert AFTER INSERT ON approval_steps
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'approval_steps', NEW.approval_step_id,
        NULL, JSON_OBJECT(
            'approval_step_id', NEW.approval_step_id,
            'approval_request_id', NEW.approval_request_id,
            'step_order', NEW.step_order,
            'approver_user_id', NEW.approver_user_id,
            'status', NEW.status,
            'comments', NEW.comments,
            'decided_at', NEW.decided_at,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_approval_steps_after_update AFTER UPDATE ON approval_steps
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'approval_steps', NEW.approval_step_id,
        JSON_OBJECT(
            'approval_step_id', OLD.approval_step_id,
            'approval_request_id', OLD.approval_request_id,
            'step_order', OLD.step_order,
            'approver_user_id', OLD.approver_user_id,
            'status', OLD.status,
            'comments', OLD.comments,
            'decided_at', OLD.decided_at,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'approval_step_id', NEW.approval_step_id,
            'approval_request_id', NEW.approval_request_id,
            'step_order', NEW.step_order,
            'approver_user_id', NEW.approver_user_id,
            'status', NEW.status,
            'comments', NEW.comments,
            'decided_at', NEW.decided_at,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_approval_steps_after_delete AFTER DELETE ON approval_steps
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'approval_steps', OLD.approval_step_id,
        JSON_OBJECT(
            'approval_step_id', OLD.approval_step_id,
            'approval_request_id', OLD.approval_request_id,
            'step_order', OLD.step_order,
            'approver_user_id', OLD.approver_user_id,
            'status', OLD.status,
            'comments', OLD.comments,
            'decided_at', OLD.decided_at,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_documents_after_insert AFTER INSERT ON documents
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'documents', NEW.document_id,
        NULL, JSON_OBJECT(
            'document_id', NEW.document_id,
            'employee_id', NEW.employee_id,
            'document_type', NEW.document_type,
            'file_name', NEW.file_name,
            'file_path', NEW.file_path,
            'issued_by_user_id', NEW.issued_by_user_id,
            'issued_at', NEW.issued_at,
            'created_at', NEW.created_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_documents_after_update AFTER UPDATE ON documents
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'documents', NEW.document_id,
        JSON_OBJECT(
            'document_id', OLD.document_id,
            'employee_id', OLD.employee_id,
            'document_type', OLD.document_type,
            'file_name', OLD.file_name,
            'file_path', OLD.file_path,
            'issued_by_user_id', OLD.issued_by_user_id,
            'issued_at', OLD.issued_at,
            'created_at', OLD.created_at
        ), JSON_OBJECT(
            'document_id', NEW.document_id,
            'employee_id', NEW.employee_id,
            'document_type', NEW.document_type,
            'file_name', NEW.file_name,
            'file_path', NEW.file_path,
            'issued_by_user_id', NEW.issued_by_user_id,
            'issued_at', NEW.issued_at,
            'created_at', NEW.created_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_documents_after_delete AFTER DELETE ON documents
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'documents', OLD.document_id,
        JSON_OBJECT(
            'document_id', OLD.document_id,
            'employee_id', OLD.employee_id,
            'document_type', OLD.document_type,
            'file_name', OLD.file_name,
            'file_path', OLD.file_path,
            'issued_by_user_id', OLD.issued_by_user_id,
            'issued_at', OLD.issued_at,
            'created_at', OLD.created_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

DELIMITER ;
