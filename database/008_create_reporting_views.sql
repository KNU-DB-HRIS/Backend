CREATE VIEW vw_employee_directory AS
SELECT
    e.employee_id, e.company_id, c.company_name AS company_name,
    e.employee_no, e.employee_name AS employee_name,
    e.hire_date, e.employment_type, e.employment_status,
    e.department_id, d.department_code, d.department_name,
    e.position_id, p.position_code, p.position_name, p.position_level AS position_level,
    e.job_id, j.job_code, j.job_name,
    e.job_title_id, t.job_title_code, t.job_title_name
FROM employees e
JOIN companies c ON c.company_id = e.company_id
JOIN departments d ON d.department_id = e.department_id
JOIN positions p ON p.position_id = e.position_id
JOIN jobs j ON j.job_id = e.job_id
LEFT JOIN job_titles t ON t.job_title_id = e.job_title_id;

CREATE VIEW vw_current_salaries AS
SELECT e.employee_id, e.company_id, e.employee_no, e.employee_name AS employee_name,
       e.current_salary, e.updated_at AS last_employee_update
FROM employees e;

CREATE VIEW vw_department_headcount AS
SELECT d.company_id, d.department_id, d.department_code, d.department_name,
       d.is_active,
       COUNT(CASE WHEN e.employment_status = 'ACTIVE' THEN 1 END) AS active_headcount
FROM departments d
LEFT JOIN employees e ON e.department_id = d.department_id
GROUP BY d.company_id, d.department_id, d.department_code, d.department_name, d.is_active;

CREATE VIEW vw_position_headcount AS
SELECT p.company_id, p.position_id, p.position_code, p.position_name,
       p.position_level AS position_level, p.is_active,
       COUNT(CASE WHEN e.employment_status = 'ACTIVE' THEN 1 END) AS active_headcount
FROM positions p
LEFT JOIN employees e ON e.position_id = p.position_id
GROUP BY p.company_id, p.position_id, p.position_code, p.position_name, p.position_level, p.is_active;

CREATE VIEW vw_assignment_timeline AS
SELECT a.assignment_history_id, a.employee_id, e.employee_no, e.employee_name AS employee_name,
       a.action_type, a.action_date, a.effective_date,
       a.from_department_id, fd.department_name AS from_department_name,
       a.to_department_id, td.department_name AS to_department_name,
       a.from_position_id, fp.position_name AS from_position_name,
       a.to_position_id, tp.position_name AS to_position_name,
       a.from_job_id, fj.job_name AS from_job_name,
       a.to_job_id, tj.job_name AS to_job_name,
       a.from_job_title_id, ft.job_title_name AS from_job_title_name,
       a.to_job_title_id, tt.job_title_name AS to_job_title_name,
       a.reason, a.document_url, a.created_by_user_id
FROM assignment_history a
JOIN employees e ON e.employee_id = a.employee_id
LEFT JOIN departments fd ON fd.department_id = a.from_department_id
LEFT JOIN departments td ON td.department_id = a.to_department_id
LEFT JOIN positions fp ON fp.position_id = a.from_position_id
LEFT JOIN positions tp ON tp.position_id = a.to_position_id
LEFT JOIN jobs fj ON fj.job_id = a.from_job_id
LEFT JOIN jobs tj ON tj.job_id = a.to_job_id
LEFT JOIN job_titles ft ON ft.job_title_id = a.from_job_title_id
LEFT JOIN job_titles tt ON tt.job_title_id = a.to_job_title_id;

CREATE VIEW vw_salary_timeline AS
SELECT h.salary_history_id, h.employee_id, e.employee_no,
       h.previous_salary, h.new_salary, h.effective_date, h.reason,
       h.changed_by_user_id, h.created_at
FROM salary_history h
JOIN employees e ON e.employee_id = h.employee_id;

CREATE VIEW vw_employee_evaluation_results AS
SELECT ev.employee_evaluation_id, ev.employee_id, e.employee_no, e.employee_name AS employee_name,
       ev.evaluator_employee_id, r.employee_name AS evaluator_name,
       ep.evaluation_period_id, ep.evaluation_year, ep.evaluation_half,
       ev.score, ev.grade, ev.comments, ev.status,
       ev.evaluated_at
FROM employee_evaluations ev
JOIN employees e ON e.employee_id = ev.employee_id
JOIN employees r ON r.employee_id = ev.evaluator_employee_id
JOIN evaluation_periods ep ON ep.evaluation_period_id = ev.evaluation_period_id;

CREATE VIEW vw_user_effective_permissions AS
SELECT DISTINCT u.user_id, u.username, r.role_code, p.permission_code,
       p.resource_type, p.action_type
FROM users u
JOIN user_roles ur ON ur.user_id = u.user_id
JOIN roles r ON r.role_id = ur.role_id AND r.is_active = TRUE
JOIN role_permissions rp ON rp.role_id = r.role_id
JOIN permissions p ON p.permission_id = rp.permission_id AND p.is_active = TRUE
WHERE u.status = 'ACTIVE';

CREATE VIEW vw_approval_progress AS
SELECT ar.approval_request_id, ar.request_type, ar.reference_id,
       ar.requester_user_id, ar.title, ar.status AS request_status,
       COUNT(ast.approval_step_id) AS step_count,
       COUNT(CASE WHEN ast.status = 'APPROVED' THEN 1 END) AS approved_step_count,
       COUNT(CASE WHEN ast.status = 'REJECTED' THEN 1 END) AS rejected_step_count,
       ar.requested_at, ar.completed_at
FROM approval_requests ar
LEFT JOIN approval_steps ast ON ast.approval_request_id = ar.approval_request_id
GROUP BY ar.approval_request_id, ar.request_type, ar.reference_id,
         ar.requester_user_id, ar.title, ar.status, ar.requested_at, ar.completed_at;

CREATE VIEW vw_nl_employee_directory AS
SELECT employee_id, company_id, employee_no, employee_name,
       hire_date, employment_status, department_name, position_name,
       job_name, job_title_name
FROM vw_employee_directory;

CREATE VIEW vw_nl_org_headcounts AS
SELECT company_id, department_id, department_name, active_headcount
FROM vw_department_headcount;
