ALTER TABLE departments
    ADD CONSTRAINT fk_departments_manager_employee
        FOREIGN KEY (company_id, department_id, manager_employee_id)
        REFERENCES employees (company_id, department_id, employee_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE assignment_history
    ADD CONSTRAINT fk_assignment_history_created_by_user_id
        FOREIGN KEY (created_by_user_id) REFERENCES users (user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE salary_history
    ADD CONSTRAINT fk_salary_history_changed_by_user_id
        FOREIGN KEY (changed_by_user_id) REFERENCES users (user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
