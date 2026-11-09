import json
import sys
from datetime import datetime, time, timedelta

import click
from flask import current_app
from flask.cli import with_appcontext

from app.db import all_rows, execute, insert, one, scalar, today, transaction, update
from app.security import create_account

COMPANY_NUMBER = "999-99-99999"
MENUS = (
    ("DASHBOARD", "대시보드"),
    ("EMPLOYEES", "인사 관리"),
    ("PAYROLL", "급여 관리"),
    ("ORGANIZATION", "조직 관리"),
    ("EVALUATION", "평가 관리"),
    ("DOCUMENTS", "전자 문서"),
    ("AI", "HR AI"),
)
DEPARTMENTS = (
    ("HR", "인사팀"),
    ("DEV", "개발팀"),
    ("DESIGN", "디자인팀"),
    ("SALES", "영업팀"),
    ("OPS", "경영지원팀"),
)
POSITIONS = (("STAFF", "사원"), ("ASSOC", "대리"), ("MANAGER", "과장"),
             ("DIRECTOR", "차장"), ("HEAD", "부장"))
JOBS = (("HR", "인사 운영"), ("DEV", "서비스 개발"), ("DESIGN", "제품 디자인"),
        ("SALES", "영업 운영"), ("OPS", "경영 지원"))
PEOPLE = (
    ("admin01", "김서연", "HR", "MANAGER", "HR", "LEAD", 1600, 6200000, "ACTIVE"),
    ("employee02", "이도윤", "DEV", "ASSOC", "DEV", "LEAD", 1000, 4800000, "ACTIVE"),
    ("employee03", "박하린", "DEV", "STAFF", "DEV", "MEMBER", 720, 3800000, "ACTIVE"),
    ("employee04", "정민준", "DESIGN", "ASSOC", "DESIGN", "LEAD", 540, 4600000, "ACTIVE"),
    ("employee05", "최유진", "SALES", "MANAGER", "SALES", "LEAD", 420, 5300000, "ACTIVE"),
    ("employee06", "윤지호", "OPS", "STAFF", "OPS", "LEAD", 310, 3600000, "ACTIVE"),
    ("employee07", "한수빈", "HR", "STAFF", "HR", "MEMBER", 210, 3400000, "ACTIVE"),
    ("employee08", "오서준", "DEV", "STAFF", "DEV", "MEMBER", 150, 3700000, "ACTIVE"),
    ("employee09", "김나연", "SALES", "STAFF", "SALES", "MEMBER", 90, 3500000, "ACTIVE"),
    ("employee10", "송지우", "OPS", "ASSOC", "OPS", "MEMBER", 60, 4100000, "ON_LEAVE"),
)
STAGES = ("GOAL", "SELF", "PEER", "LEADER")


def add_roles(conn):
    ids = {}
    for code, name in (("HR_ADMIN", "HR 관리자"), ("EMPLOYEE", "사원")):
        execute(conn, "INSERT IGNORE INTO roles(role_code,role_name,is_active) VALUES(:code,:name,1)",
                {"code": code, "name": name})
        ids[code] = scalar(conn, "SELECT role_id FROM roles WHERE role_code=:code AND is_active=1",
                           {"code": code})
        if not ids[code]:
            raise click.ClickException(f"Role is inactive: {code}")
    for menu, name in MENUS:
        code = f"MENU_{menu}"
        execute(conn,
                "INSERT IGNORE INTO permissions(permission_code,permission_name,resource_type,action_type,is_active) "
                "VALUES(:code,:name,'menu','VIEW',1)", {"code": code, "name": name})
        for role_code in (("HR_ADMIN", "EMPLOYEE") if menu == "DOCUMENTS" else ("HR_ADMIN",)):
            execute(conn,
                    "INSERT IGNORE INTO role_permissions(role_id,permission_id) "
                    "SELECT r.role_id,p.permission_id FROM roles r JOIN permissions p "
                    "ON p.permission_code=:permission WHERE r.role_code=:role AND r.is_active=1 AND p.is_active=1",
                    {"permission": code, "role": role_code})
    return ids


def add_references(conn, company_id):
    departments = {}
    for code, name in DEPARTMENTS:
        departments[code] = insert(conn, "departments", {
            "company_id": company_id, "department_code": f"DEP-{code}", "department_name": name,
            "description": f"{name} 샘플 부서",
        })
    positions = {}
    for level, (code, name) in enumerate(POSITIONS, 1):
        positions[code] = insert(conn, "positions", {
            "company_id": company_id, "position_code": f"POS-{code}",
            "position_name": name, "position_level": level,
        })
    jobs = {}
    for code, name in JOBS:
        jobs[code] = insert(conn, "jobs", {
            "company_id": company_id, "job_code": f"JOB-{code}",
            "job_name": name, "job_category": code, "job_family": code,
        })
    titles = {}
    for code, name in (("LEAD", "팀장"), ("MEMBER", "팀원")):
        titles[code] = insert(conn, "job_titles", {
            "company_id": company_id, "job_title_code": f"TITLE-{code}",
            "job_title_name": name,
        })
    return departments, positions, jobs, titles


def components(salary):
    return {
        "base_salary": salary - 300000,
        "position_allowance": 100000,
        "meal_allowance": 200000,
        "other_allowance": 0,
    }


def add_people(conn, company_id, reference, role_ids, passwords):
    departments, positions, jobs, titles = reference
    employees, users = {}, {}
    for index, (username, name, department, position, job, title, tenure, salary, status) in enumerate(PEOPLE, 1):
        hire_date = today() - timedelta(days=tenure)
        employee_id = insert(conn, "employees", {
            "company_id": company_id, "employee_no": f"EMP{index:03d}",
            "employee_name": name, "email": f"{username}@example.test",
            "phone": f"010-0000-{index:04d}", "hire_date": hire_date,
            "employment_type": "FULL_TIME", "employment_status": status,
            "department_id": departments[department], "position_id": positions[position],
            "job_id": jobs[job], "job_title_id": titles[title],
            "current_salary": salary, "address": "가상 데이터 (개발용)",
        })
        employees[username] = employee_id
        if index == 1:
            role_code = "HR_ADMIN"
        else:
            role_code = "EMPLOYEE"
        users[username] = create_account(conn, employee_id, username, passwords[username], role_ids[role_code])
        if index == 1:
            execute(conn, "SET @hris_actor_user_id=:actor", {"actor": users[username]})
        insert(conn, "assignment_history", {
            "employee_id": employee_id, "action_type": "HIRE", "action_date": hire_date,
            "effective_date": hire_date, "to_department_id": departments[department],
            "to_position_id": positions[position], "to_job_id": jobs[job],
            "to_job_title_id": titles[title], "reason": "샘플 입사 등록",
            "created_by_user_id": users["admin01"],
        })
        initial_date = hire_date
        initial_salary = salary - 200000 if tenure > 365 else salary
        insert(conn, "salary_history", {
            "employee_id": employee_id, "previous_salary": None, "new_salary": initial_salary,
            "effective_date": initial_date, "reason": "샘플 초기 급여",
            "changed_by_user_id": users["admin01"], **components(initial_salary),
            "components_status": "COMPLETE",
        })
        if initial_salary != salary:
            insert(conn, "salary_history", {
                "employee_id": employee_id, "previous_salary": initial_salary, "new_salary": salary,
                "effective_date": max(hire_date + timedelta(days=365), today() - timedelta(days=75)),
                "reason": "정기 급여 조정 (샘플)", "changed_by_user_id": users["admin01"],
                **components(salary), "components_status": "COMPLETE",
            })
    for code, username in (("HR", "admin01"), ("DEV", "employee02"),
                           ("DESIGN", "employee04"), ("SALES", "employee05"),
                           ("OPS", "employee06")):
        update(conn, "departments", "department_id", departments[code],
               {"manager_employee_id": employees[username]})
    return employees, users


def add_payroll(conn, employees):
    first = today().replace(day=1)
    last_month = first - timedelta(days=1)
    pay_month = last_month.strftime("%Y-%m")
    for person in PEOPLE:
        username, _, _, _, _, _, _, salary, _ = person
        fields = components(salary)
        deductions = {
            "national_pension": int(salary * 0.045),
            "health_insurance": int(salary * 0.035),
            "long_term_care": int(salary * 0.0045),
            "employment_insurance": int(salary * 0.009),
            "income_tax": int(salary * 0.025),
            "local_income_tax": int(salary * 0.0025),
        }
        total = sum(deductions.values())
        insert(conn, "payroll_statements", {
            "employee_id": employees[username], "pay_month": pay_month,
            **fields, "gross_pay": salary, **deductions, "total_deduction": total,
            "net_pay": salary - total, "status": "PAID", "paid_at": last_month,
        })


def add_attendance(conn, employees):
    day = today().replace(day=1)
    while day <= today():
        if day.weekday() < 5:
            for index, person in enumerate(PEOPLE, 1):
                username, _, _, _, _, _, _, _, status = person
                if status == "ON_LEAVE":
                    continue
                attendance = "ABSENT" if (day.day + index) % 29 == 0 else (
                    "LEAVE" if (day.day + index) % 17 == 0 else "PRESENT"
                )
                insert(conn, "attendance_records", {
                    "employee_id": employees[username], "work_date": day,
                    "status": attendance,
                    "check_in_at": datetime.combine(day, time(9, index % 30))
                    if attendance == "PRESENT" else None,
                })
        day += timedelta(days=1)


def add_evaluations(conn, company_id, employees):
    day = today()
    half = "H1" if day.month <= 6 else "H2"
    year = day.year
    period_start = day.replace(month=1 if half == "H1" else 7, day=1)
    period_id = insert(conn, "evaluation_periods", {
        "company_id": company_id, "evaluation_year": year, "evaluation_half": half,
        "start_date": period_start,
        "end_date": day.replace(month=6 if half == "H1" else 12, day=30 if half == "H1" else 31),
        "status": "IN_PROGRESS",
    })
    grades = ("A", "B", None, "S", "B", "A", None, "B", None, None)
    for index, person in enumerate(PEOPLE):
        username = person[0]
        stages_done = [4, 3, 2, 4, 3, 4, 1, 3, 0, 0][index]
        score = [90, 82, None, 96, 84, 91, None, 86, None, None][index]
        evaluation_id = insert(conn, "employee_evaluations", {
            "employee_id": employees[username],
            "evaluator_employee_id": employees["employee05" if username == "admin01" else "admin01"],
            "evaluation_period_id": period_id, "score": score, "grade": grades[index],
            "status": "COMPLETED" if stages_done == 4 else "IN_PROGRESS",
            "evaluated_at": datetime.combine(today() - timedelta(days=2), time(16, 0))
            if stages_done == 4 else None,
        })
        for stage_no in range(stages_done):
            insert(conn, "evaluation_stage_records", {
                "evaluation_id": evaluation_id, "stage": STAGES[stage_no],
                "evaluator_id": employees[username] if stage_no == 1 else employees["admin01"],
                "score": 85 + ((index + stage_no) % 12),
                "comment": "평가 진행 샘플",
                "submitted_at": datetime.combine(max(period_start, today() - timedelta(days=10 - stage_no)), time(14, 0)),
            })


def add_approvals(conn, users):
    data = (
        ("employee03", "LEAVE", "연차 휴가 신청", "IN_PROGRESS", ("admin01", "employee05")),
        ("employee07", "EXPENSE", "교육비 지원 요청", "APPROVED", ("admin01",)),
        ("employee04", "BUSINESS_TRIP", "출장 계획 승인", "REJECTED", ("admin01",)),
        ("employee02", "GENERAL", "개발팀 장비 구매 제안", "DRAFT", ("admin01",)),
    )
    for requester, kind, title, status, approvers in data:
        request_id = insert(conn, "approval_requests", {
            "requester_user_id": users[requester], "request_type": kind,
            "title": title, "content": "샘플 전자결재 문서입니다.", "status": status,
        })
        for order, approver in enumerate(approvers, 1):
            step_status = ("APPROVED" if status == "APPROVED" else
                           "REJECTED" if status == "REJECTED" else
                           "PENDING" if status == "IN_PROGRESS" and order == 1 else "WAITING")
            insert(conn, "approval_steps", {
                "approval_request_id": request_id, "step_order": order,
                "approver_user_id": users[approver], "status": step_status,
            })


def add_events(conn, company_id):
    for days, title, target in (
        (1, "채용 면접 일정", "인사팀"),
        (5, "월간 조직 운영 회의", "전사"),
        (12, "성과 평가 중간 점검", "각 부서"),
    ):
        event_date = today() + timedelta(days=days)
        insert(conn, "hr_events", {
            "company_id": company_id, "title": title, "target": target,
            "start_at": datetime.combine(event_date, time(10, 0)),
            "end_at": datetime.combine(event_date, time(11, 0)),
            "location": "샘플 회의실", "all_day": False,
        })


@click.command("db-seed-demo")
@with_appcontext
def db_seed_demo():
    if current_app.config["APP_ENV"] != "development":
        raise click.ClickException("Sample data can only be loaded when APP_ENV=development")
    try:
        passwords = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise click.ClickException("Missing or invalid credentials input") from exc
    expected = {person[0] for person in PEOPLE}
    if not isinstance(passwords, dict) or set(passwords) != expected or any(
        not isinstance(p, str) or not 12 <= len(p) <= 128 for p in passwords.values()
    ):
        raise click.ClickException("Expected exactly 10 valid sample user passwords")
    with transaction() as conn:
        existing = one(conn, "SELECT company_id FROM companies WHERE business_number=:number",
                       {"number": COMPANY_NUMBER})
        if existing:
            users = all_rows(conn,
                "SELECT u.username FROM users u JOIN employees e ON e.employee_id=u.employee_id "
                "WHERE e.company_id=:company", {"company": existing["company_id"]})
            employee_count = scalar(conn, "SELECT COUNT(*) FROM employees WHERE company_id=:company",
                                    {"company": existing["company_id"]})
            if employee_count == 10 and {row["username"] for row in users} == expected:
                click.echo("Sample data already present. No records or passwords were changed.")
                return
            raise click.ClickException("Sample company exists but is incomplete or modified. No changes made.")
        if any(scalar(conn, f"SELECT COUNT(*) FROM {table}") for table in ("companies", "employees", "users")):
            raise click.ClickException("Refusing to seed a non-empty database. Use a fresh development DB.")
        role_ids = add_roles(conn)
        company_id = insert(conn, "companies", {
            "company_name": "샘플테크", "name_en": "SampleTech",
            "business_number": COMPANY_NUMBER, "address": "가상 주소 (개발용)",
            "phone": "02-0000-0000", "email": "hr@example.test",
            "industry": "소프트웨어 개발", "ceo_name": "김서연",
        })
        reference = add_references(conn, company_id)
        employees, users = add_people(conn, company_id, reference, role_ids, passwords)
        add_payroll(conn, employees)
        add_attendance(conn, employees)
        add_evaluations(conn, company_id, employees)
        add_approvals(conn, users)
        add_events(conn, company_id)
    click.echo("Sample data created: 1 company, 5 departments, 10 employees/users, plus payroll, attendance, evaluations, approvals and events.")
