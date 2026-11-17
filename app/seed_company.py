"""계열사 샘플 데이터 (개발용): 이미 만든 빈 회사에 부서, 직원 N명, 급여, 근태, 평가, 결재, 일정을 넣는다.

setup/database-company-data.sh 가 호스트에서 계정 비밀번호를 만들어 stdin(JSON)으로 넘긴다.
기존 db-seed-demo(샘플테크)와 같은 규칙: APP_ENV=development 에서만, 한 트랜잭션, 실패 시 전부 롤백.
"""
import json
import sys
from datetime import datetime, time, timedelta

import click
from flask import current_app
from flask.cli import with_appcontext

from app.db import execute, insert, one, scalar, today, transaction, update
from app.security import create_account
from app.seed_demo import STAGES, add_roles, components

DEPARTMENTS = (
    ("CONTENT", "콘텐츠기획팀"),
    ("VIDEO", "영상제작팀"),
    ("MKT", "마케팅팀"),
    ("DESIGN", "디자인팀"),
    ("OPS", "경영지원팀"),
)
POSITIONS = (("STAFF", "사원"), ("ASSOC", "대리"), ("MANAGER", "과장"), ("DIRECTOR", "차장"), ("HEAD", "부장"))
JOBS = (
    ("CONTENT", "콘텐츠 기획"),
    ("VIDEO", "영상 제작"),
    ("MKT", "마케팅"),
    ("DESIGN", "시각 디자인"),
    ("OPS", "경영 지원"),
)
NAMES = (
    "강민지", "조현우", "윤서아", "장도현", "임채원", "신우진", "배수아", "권태윤", "홍지안", "문예린",
    "서준호", "유하은", "남시우", "고은채", "백승민", "송다인", "안지훈", "황보라", "전예준", "노하윤",
    "표서진", "하도경", "제민서", "왕지율", "탁은호", "변소윤", "추시온", "도하람", "봉지환", "엄채아",
)
BASE_SALARY = {"STAFF": 3500000, "ASSOC": 4400000, "MANAGER": 5400000, "DIRECTOR": 6200000, "HEAD": 7000000}
# 앞의 5명은 부서장(첫 번째는 이 회사의 인사관리자)
LEADS = (("OPS", "MANAGER", 1500), ("CONTENT", "HEAD", 2400), ("VIDEO", "DIRECTOR", 1900),
         ("MKT", "MANAGER", 1200), ("DESIGN", "MANAGER", 980))
MEMBER_ORDER = ("CONTENT", "VIDEO", "MKT", "DESIGN", "OPS")


def plan_people(size, prefix):
    people = []
    for i in range(size):
        if i < len(LEADS):
            department, position, tenure = LEADS[i]
            title = "LEAD"
        else:
            department = MEMBER_ORDER[i % len(MEMBER_ORDER)]
            position = "ASSOC" if i % 3 == 0 else "STAFF"
            tenure = 30 + (i * 97) % 1400
            title = "MEMBER"
        status = "ON_LEAVE" if size >= 10 and i == size - 3 else "ACTIVE"
        people.append({
            "username": f"{prefix}{i + 1:02d}", "name": NAMES[i], "department": department,
            "position": position, "job": department, "title": title, "tenure": tenure,
            "salary": BASE_SALARY[position] + (i % 4) * 100000, "status": status,
        })
    return people


def add_company_references(conn, company_id):
    departments = {code: insert(conn, "departments", {
        "company_id": company_id, "department_code": f"DEP-{code}", "department_name": name,
        "description": f"{name} 샘플 부서",
    }) for code, name in DEPARTMENTS}
    positions = {code: insert(conn, "positions", {
        "company_id": company_id, "position_code": f"POS-{code}", "position_name": name, "position_level": level,
    }) for level, (code, name) in enumerate(POSITIONS, 1)}
    jobs = {code: insert(conn, "jobs", {
        "company_id": company_id, "job_code": f"JOB-{code}", "job_name": name,
        "job_category": code, "job_family": code,
    }) for code, name in JOBS}
    titles = {code: insert(conn, "job_titles", {
        "company_id": company_id, "job_title_code": f"TITLE-{code}", "job_title_name": name,
    }) for code, name in (("LEAD", "팀장"), ("MEMBER", "팀원"))}
    return departments, positions, jobs, titles


@click.command("db-seed-company")
@click.option("--company-id", type=int, required=True, help="데이터를 넣을 회사 (직원이 없는 활성 회사)")
@click.option("--size", type=click.IntRange(5, len(NAMES)), default=20, show_default=True, help="직원 수")
@click.option("--prefix", default="media", show_default=True, help="계정 아이디, 이메일 앞부분 (prefix01 ...)")
@with_appcontext
def db_seed_company(company_id, size, prefix):
    if current_app.config["APP_ENV"] != "development":
        raise click.ClickException("Sample data can only be loaded when APP_ENV=development")
    if not prefix.isalnum() or not prefix.isascii() or len(prefix) > 20:
        raise click.ClickException("--prefix must be 1-20 ASCII letters/digits")
    try:
        passwords = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise click.ClickException("Missing or invalid credentials input") from exc
    people = plan_people(size, prefix)
    accounts = [p["username"] for p in people[:3]]  # 인사관리자 1 + 사원 2
    if not isinstance(passwords, dict) or set(passwords) != set(accounts) or any(
        not isinstance(v, str) or not 12 <= len(v) <= 128 for v in passwords.values()
    ):
        raise click.ClickException(f"Expected passwords for exactly: {', '.join(accounts)}")
    with transaction() as conn:
        company = one(conn, "SELECT company_id,company_name,is_active FROM companies WHERE company_id=:id",
                      {"id": company_id})
        if not company or not company["is_active"]:
            raise click.ClickException("Company not found or inactive")
        if scalar(conn, "SELECT COUNT(*) FROM employees WHERE company_id=:id", {"id": company_id}):
            raise click.ClickException("Company already has employees. No changes made.")
        if scalar(conn, "SELECT COUNT(*) FROM departments WHERE company_id=:id", {"id": company_id}):
            raise click.ClickException("Company already has departments. Use an empty company.")
        emails = [f"{p['username']}@example.test" for p in people]
        taken = sum(scalar(conn, "SELECT COUNT(*) FROM employees WHERE email=:e", {"e": e}) for e in emails)
        if taken or any(scalar(conn, "SELECT COUNT(*) FROM users WHERE username=:u", {"u": u}) for u in accounts):
            raise click.ClickException(f"Prefix '{prefix}' already used (email or username). Choose another --prefix.")
        role_ids = add_roles(conn)
        departments, positions, jobs, titles = add_company_references(conn, company_id)
        employees, users = {}, {}
        for index, p in enumerate(people, 1):
            hire_date = today() - timedelta(days=p["tenure"])
            employee_id = insert(conn, "employees", {
                "company_id": company_id, "employee_no": f"EMP{index:03d}", "employee_name": p["name"],
                "email": f"{p['username']}@example.test", "phone": f"010-{company_id % 10000:04d}-{index:04d}",
                "hire_date": hire_date, "employment_type": "FULL_TIME" if index % 7 else "CONTRACT",
                "employment_status": p["status"], "department_id": departments[p["department"]],
                "position_id": positions[p["position"]], "job_id": jobs[p["job"]], "job_title_id": titles[p["title"]],
                "current_salary": p["salary"], "address": "가상 데이터 (개발용)",
            })
            employees[p["username"]] = employee_id
            if p["username"] in accounts:
                role = "HR_ADMIN" if index == 1 else "EMPLOYEE"
                users[p["username"]] = create_account(conn, employee_id, p["username"], passwords[p["username"]], role_ids[role])
                if index == 1:
                    execute(conn, "SET @hris_actor_user_id=:actor", {"actor": users[p["username"]]})
            admin_user = users[accounts[0]]
            insert(conn, "assignment_history", {
                "employee_id": employee_id, "action_type": "HIRE", "action_date": hire_date, "effective_date": hire_date,
                "to_department_id": departments[p["department"]], "to_position_id": positions[p["position"]],
                "to_job_id": jobs[p["job"]], "to_job_title_id": titles[p["title"]], "reason": "샘플 입사 등록",
                "created_by_user_id": admin_user,
            })
            initial = p["salary"] - 200000 if p["tenure"] > 365 else p["salary"]
            insert(conn, "salary_history", {
                "employee_id": employee_id, "previous_salary": None, "new_salary": initial, "effective_date": hire_date,
                "reason": "샘플 초기 급여", "changed_by_user_id": admin_user, **components(initial),
                "components_status": "COMPLETE",
            })
            if initial != p["salary"]:
                insert(conn, "salary_history", {
                    "employee_id": employee_id, "previous_salary": initial, "new_salary": p["salary"],
                    "effective_date": max(hire_date + timedelta(days=365), today() - timedelta(days=75)),
                    "reason": "정기 급여 조정 (샘플)", "changed_by_user_id": admin_user, **components(p["salary"]),
                    "components_status": "COMPLETE",
                })
        for p in people[: len(LEADS)]:
            update(conn, "departments", "department_id", departments[p["department"]],
                   {"manager_employee_id": employees[p["username"]]})

        # 지난달 급여 (지난달 말 이전 입사자)
        first = today().replace(day=1)
        last_month = first - timedelta(days=1)
        for p in people:
            if today() - timedelta(days=p["tenure"]) > last_month:
                continue
            salary = p["salary"]
            deductions = {
                "national_pension": int(salary * 0.045), "health_insurance": int(salary * 0.035),
                "long_term_care": int(salary * 0.0045), "employment_insurance": int(salary * 0.009),
                "income_tax": int(salary * 0.025), "local_income_tax": int(salary * 0.0025),
            }
            total = sum(deductions.values())
            insert(conn, "payroll_statements", {
                "employee_id": employees[p["username"]], "pay_month": last_month.strftime("%Y-%m"),
                **components(salary), "gross_pay": salary, **deductions, "total_deduction": total,
                "net_pay": salary - total, "status": "PAID", "paid_at": last_month,
            })

        # 이번 달 근태 (재직자, 평일)
        day = first
        while day <= today():
            if day.weekday() < 5:
                for index, p in enumerate(people, 1):
                    if p["status"] != "ACTIVE" or day < today() - timedelta(days=p["tenure"]):
                        continue
                    status = "ABSENT" if (day.day + index) % 29 == 0 else ("LEAVE" if (day.day + index) % 13 == 0 else "PRESENT")
                    insert(conn, "attendance_records", {
                        "employee_id": employees[p["username"]], "work_date": day, "status": status,
                        "check_in_at": datetime.combine(day, time(8 + index % 2, (index * 7) % 60)) if status == "PRESENT" else None,
                    })
            day += timedelta(days=1)

        # 이번 반기 평가
        now_day = today()
        half = "H1" if now_day.month <= 6 else "H2"
        period_start = now_day.replace(month=1 if half == "H1" else 7, day=1)
        if not scalar(conn, "SELECT COUNT(*) FROM evaluation_periods WHERE company_id=:c AND evaluation_year=:y AND evaluation_half=:h",
                      {"c": company_id, "y": now_day.year, "h": half}):
            period_id = insert(conn, "evaluation_periods", {
                "company_id": company_id, "evaluation_year": now_day.year, "evaluation_half": half,
                "start_date": period_start,
                "end_date": now_day.replace(month=6 if half == "H1" else 12, day=30 if half == "H1" else 31),
                "status": "IN_PROGRESS",
            })
            admin_employee = employees[accounts[0]]
            for index, p in enumerate(people):
                stages_done = (4, 3, 2, 4, 1, 0)[index % 6]
                score = 80 + (index * 7) % 18 if stages_done == 4 else None
                grade = None if score is None else ("S" if score >= 95 else "A" if score >= 88 else "B")
                evaluation_id = insert(conn, "employee_evaluations", {
                    "employee_id": employees[p["username"]],
                    "evaluator_employee_id": employees[people[1]["username"]] if index == 0 else admin_employee,
                    "evaluation_period_id": period_id, "score": score, "grade": grade,
                    "status": "COMPLETED" if stages_done == 4 else "IN_PROGRESS",
                    "evaluated_at": datetime.combine(now_day - timedelta(days=2), time(16, 0)) if stages_done == 4 else None,
                })
                for stage_no in range(stages_done):
                    insert(conn, "evaluation_stage_records", {
                        "evaluation_id": evaluation_id, "stage": STAGES[stage_no],
                        "evaluator_id": employees[p["username"]] if stage_no == 1 else admin_employee,
                        "score": 84 + ((index + stage_no) % 12), "comment": "평가 진행 샘플",
                        "submitted_at": datetime.combine(max(period_start, now_day - timedelta(days=10 - stage_no)), time(14, 0)),
                    })

        # 결재 4건 (사원 2명이 기안, 인사관리자가 결재)
        admin, staff1, staff2 = (users[u] for u in accounts)
        for requester, kind, title, status in (
            (staff1, "LEAVE", "연차 휴가 신청", "IN_PROGRESS"), (staff2, "EXPENSE", "촬영 장비 대여비 정산", "APPROVED"),
            (staff1, "BUSINESS_TRIP", "지방 촬영 출장 승인", "REJECTED"), (staff2, "GENERAL", "콘텐츠 제작 일정 협의", "DRAFT"),
        ):
            request_id = insert(conn, "approval_requests", {
                "requester_user_id": requester, "request_type": kind, "title": title,
                "content": "샘플 전자결재 문서입니다.", "status": status,
            })
            insert(conn, "approval_steps", {
                "approval_request_id": request_id, "step_order": 1, "approver_user_id": admin,
                "status": {"APPROVED": "APPROVED", "REJECTED": "REJECTED", "IN_PROGRESS": "PENDING"}.get(status, "WAITING"),
            })

        for days, title, target in ((2, "신규 콘텐츠 기획 회의", "콘텐츠기획팀"), (6, "분기 영상 성과 리뷰", "전사"),
                                    (14, "브랜드 캠페인 킥오프", "마케팅팀")):
            event_date = today() + timedelta(days=days)
            insert(conn, "hr_events", {
                "company_id": company_id, "title": title, "target": target,
                "start_at": datetime.combine(event_date, time(10, 0)), "end_at": datetime.combine(event_date, time(11, 0)),
                "location": "샘플 회의실", "all_day": False,
            })
    click.echo(
        f"Sample data created for {company['company_name']}: {len(DEPARTMENTS)} departments, {size} employees "
        f"({len(accounts)} accounts: {', '.join(accounts)}), payroll, attendance, evaluations, approvals and events."
    )
