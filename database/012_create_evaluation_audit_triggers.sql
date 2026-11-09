DELIMITER $$

CREATE TRIGGER trg_evaluation_periods_after_insert AFTER INSERT ON evaluation_periods
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'evaluation_periods', NEW.evaluation_period_id,
        NULL, JSON_OBJECT(
            'evaluation_period_id', NEW.evaluation_period_id,
            'evaluation_year', NEW.evaluation_year,
            'evaluation_half', NEW.evaluation_half,
            'start_date', NEW.start_date,
            'end_date', NEW.end_date,
            'status', NEW.status,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_evaluation_periods_after_update AFTER UPDATE ON evaluation_periods
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'evaluation_periods', NEW.evaluation_period_id,
        JSON_OBJECT(
            'evaluation_period_id', OLD.evaluation_period_id,
            'evaluation_year', OLD.evaluation_year,
            'evaluation_half', OLD.evaluation_half,
            'start_date', OLD.start_date,
            'end_date', OLD.end_date,
            'status', OLD.status,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'evaluation_period_id', NEW.evaluation_period_id,
            'evaluation_year', NEW.evaluation_year,
            'evaluation_half', NEW.evaluation_half,
            'start_date', NEW.start_date,
            'end_date', NEW.end_date,
            'status', NEW.status,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_evaluation_periods_after_delete AFTER DELETE ON evaluation_periods
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'evaluation_periods', OLD.evaluation_period_id,
        JSON_OBJECT(
            'evaluation_period_id', OLD.evaluation_period_id,
            'evaluation_year', OLD.evaluation_year,
            'evaluation_half', OLD.evaluation_half,
            'start_date', OLD.start_date,
            'end_date', OLD.end_date,
            'status', OLD.status,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

CREATE TRIGGER trg_employee_evaluations_after_insert AFTER INSERT ON employee_evaluations
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'INSERT', 'employee_evaluations', NEW.employee_evaluation_id,
        NULL, JSON_OBJECT(
            'employee_evaluation_id', NEW.employee_evaluation_id,
            'employee_id', NEW.employee_id,
            'evaluator_employee_id', NEW.evaluator_employee_id,
            'evaluation_period_id', NEW.evaluation_period_id,
            'score', NEW.score,
            'grade', NEW.grade,
            'comments', NEW.comments,
            'status', NEW.status,
            'evaluated_at', NEW.evaluated_at,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_employee_evaluations_after_update AFTER UPDATE ON employee_evaluations
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'UPDATE', 'employee_evaluations', NEW.employee_evaluation_id,
        JSON_OBJECT(
            'employee_evaluation_id', OLD.employee_evaluation_id,
            'employee_id', OLD.employee_id,
            'evaluator_employee_id', OLD.evaluator_employee_id,
            'evaluation_period_id', OLD.evaluation_period_id,
            'score', OLD.score,
            'grade', OLD.grade,
            'comments', OLD.comments,
            'status', OLD.status,
            'evaluated_at', OLD.evaluated_at,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), JSON_OBJECT(
            'employee_evaluation_id', NEW.employee_evaluation_id,
            'employee_id', NEW.employee_id,
            'evaluator_employee_id', NEW.evaluator_employee_id,
            'evaluation_period_id', NEW.evaluation_period_id,
            'score', NEW.score,
            'grade', NEW.grade,
            'comments', NEW.comments,
            'status', NEW.status,
            'evaluated_at', NEW.evaluated_at,
            'created_at', NEW.created_at,
            'updated_at', NEW.updated_at
        ), @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$
CREATE TRIGGER trg_employee_evaluations_after_delete AFTER DELETE ON employee_evaluations
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (user_id, action_type, resource_type, resource_id, before_data, after_data, ip_address, created_at)
    VALUES (
        @hris_actor_user_id, 'DELETE', 'employee_evaluations', OLD.employee_evaluation_id,
        JSON_OBJECT(
            'employee_evaluation_id', OLD.employee_evaluation_id,
            'employee_id', OLD.employee_id,
            'evaluator_employee_id', OLD.evaluator_employee_id,
            'evaluation_period_id', OLD.evaluation_period_id,
            'score', OLD.score,
            'grade', OLD.grade,
            'comments', OLD.comments,
            'status', OLD.status,
            'evaluated_at', OLD.evaluated_at,
            'created_at', OLD.created_at,
            'updated_at', OLD.updated_at
        ), NULL, @hris_actor_ip_address, CURRENT_TIMESTAMP(6)
    );
END$$

DELIMITER ;
