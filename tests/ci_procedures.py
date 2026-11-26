#!/usr/bin/env python3
"""업무 프로시저(025) 검사: DB에서 직접 CALL 해서 앱과 같은 규칙으로 동작하는지 확인

usage: python3 ci_procedures.py <api_base> <Backend dir>   (샘플 데이터 db-seed-demo 필요, 비밀번호는 출력하지 않음)
- 준비 데이터(임시 직원 2명, 결재 2건)는 API로 만들고, 프로시저는 mysql CALL로 실행한 뒤 모두 지움
- sp_approve_step 결과는 앱 API(GET /approvals/{id})로도 확인해 앱과 같은 상태가 되는지 봄
"""
import atexit, csv, json, subprocess, sys, urllib.error, urllib.request, http.cookiejar, uuid
from datetime import date, timedelta
from typing import Any

API, BDIR = sys.argv[1].rstrip("/"), sys.argv[2]
CREDS = {r["username"]: r["password"] for r in csv.DictReader(open(f"{BDIR}/.seed-credentials.csv", encoding="utf-8"))}
results = []


class Client:
    def __init__(self, user):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = None
        s, _ = self.call("POST", "/auth/login", {"username": user, "password": CREDS[user]})
        assert s == 200, f"login {user} -> {s}"
        self.me = self.call("GET", "/auth/me")[1]

    def call(self, method, path, body=None) -> "tuple[int, Any]":
        req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, method=method)
        req.add_header("Content-Type", "application/json")
        if self.csrf and method != "GET":
            req.add_header("X-CSRF-Token", self.csrf)
        try:
            with self.op.open(req, timeout=60) as r:
                raw, status = r.read(), r.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        js = json.loads(raw) if raw and raw[:1] in (b"{", b"[") else None
        if isinstance(js, dict) and js.get("csrf_token"):
            self.csrf = js["csrf_token"]
        return status, js


def check(name, cond, detail: object = ""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail != "" else ""))


def mysql(q):
    r = subprocess.run(["docker", "compose", "exec", "-T", "mysql", "sh", "-c",
                        f'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -N -e "{q}"'],
                       cwd=BDIR, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip()


def call_proc(q):
    """CALL 실행. (성공 여부, 오류 메시지)"""
    out, err = mysql("SET @hris_actor_user_id = NULL, @hris_actor_ip_address = NULL; " + q)
    msg = err.split(":", 1)[-1].strip() if "ERROR" in err else ""
    return not msg, msg


tag = uuid.uuid4().hex[:4]
made = {"employees": [], "approvals": []}
admin, emp03, emp04 = Client("admin01"), Client("employee03"), Client("employee04")
today = date.today()


def cleanup():
    if made["approvals"]:
        ids = ",".join(str(int(x)) for x in made["approvals"])
        mysql(f"DELETE FROM approval_steps WHERE approval_request_id IN ({ids}); "
              f"DELETE FROM approval_requests WHERE approval_request_id IN ({ids});")
    for eid in made["employees"]:
        eid = int(eid)
        mysql(f"DELETE FROM salary_history WHERE employee_id = {eid}; DELETE FROM assignment_history WHERE employee_id = {eid}; "
              f"DELETE FROM employees WHERE employee_id = {eid};")
    left, _ = mysql(f"SELECT (SELECT COUNT(*) FROM employees WHERE email LIKE 'proc.%.{tag}@example.test') "
                    f"+ (SELECT COUNT(*) FROM approval_requests WHERE title LIKE 'E2E 프로시저 {tag}%')")
    print(f"cleanup: 임시 직원, 결재 남은 행 {left}")


atexit.register(cleanup)

deps = {d["department_name"]: d["department_id"] for d in admin.call("GET", "/departments")[1]["items"]}
pos = admin.call("GET", "/positions")[1]["items"][0]["position_id"]
job = admin.call("GET", "/jobs")[1]["items"][0]["job_id"]


def new_employee(kind):
    s, e = admin.call("POST", "/employees", {
        "name": f"프로시저{kind}", "email": f"proc.{kind}.{tag}@example.test", "phone": "010-5555-0005",
        "department_id": deps["개발팀"], "position_id": pos, "job_id": job,
        "hire_date": (today - timedelta(days=30)).isoformat(), "employment_type": "FULL_TIME"})
    if s == 201:
        made["employees"].append(e["employee_id"])
    return s, e


s1, e1 = new_employee("a")
s2, e2 = new_employee("b")
check("S1 준비: 임시 직원 2명(입사 이력만)", s1 == s2 == 201, f"{s1} {s2}")
eid, eid2 = e1["employee_id"], e2["employee_id"]
uid = admin.me["user_id"]
d5, d10 = (today - timedelta(days=5)).isoformat(), (today - timedelta(days=10)).isoformat()

# ---------------- sp_assign_employee ----------------
ok, msg = call_proc(f"CALL sp_assign_employee({eid}, 'TRANSFER', '{d5}', {deps['인사팀']}, {pos}, {job}, NULL, 'E2E 프로시저', {uid})")
dep, _ = mysql(f"SELECT department_id FROM employees WHERE employee_id = {eid}")
check("A1 sp_assign_employee 부서 이동: 현재 소속 갱신 + 이력", ok and dep == str(deps["인사팀"]), msg or dep)
ok, msg = call_proc(f"CALL sp_assign_employee({eid}, 'TRANSFER', '{d10}', {deps['개발팀']}, {pos}, {job}, NULL, 'E2E 역순', {uid})")
dep, _ = mysql(f"SELECT department_id FROM employees WHERE employee_id = {eid}")
check("A2 마지막 발령보다 앞선 날짜 거부, 소속 그대로", not ok and "latest assignment" in msg and dep == str(deps["인사팀"]), msg)
ok, msg = call_proc(f"CALL sp_assign_employee({eid}, 'LEAVE', '{d5}', {deps['인사팀']}, {pos}, {job}, NULL, 'E2E', {uid})")
check("A3 지원하지 않는 발령 종류(LEAVE) 거부", not ok and "Action type" in msg, msg)
ok, msg = call_proc(f"CALL sp_assign_employee({eid}, 'TRANSFER', '{(today - timedelta(days=40)).isoformat()}', {deps['개발팀']}, {pos}, {job}, NULL, 'E2E', {uid})")
check("A4 입사일 이전 거부", not ok and "before hire" in msg, msg)

# ---------------- sp_change_salary ----------------
ok, msg = call_proc(f"CALL sp_change_salary({eid}, 4000000, '{d5}', 'E2E 프로시저', {uid})")
cur, _ = mysql(f"SELECT CONCAT(current_salary, '/', (SELECT COUNT(*) FROM salary_history WHERE employee_id = {eid})) FROM employees WHERE employee_id = {eid}")
check("P1 sp_change_salary: 이력 + 현재 급여", ok and cur == "4000000.00/1", msg or cur)
ok, msg = call_proc(f"CALL sp_change_salary({eid}, 4100000, '{d10}', 'E2E 역순', {uid})")
check("P2 마지막 급여 이력보다 앞선 날짜 거부", not ok and "latest salary" in msg, msg)
ok, msg = call_proc(f"CALL sp_change_salary({eid}, 4100000, '{d5}', 'E2E 같은 날', {uid})")
check("P3 같은 적용일 거부", not ok and "latest salary" in msg, msg)
ok, msg = call_proc(f"CALL sp_change_salary({eid}, 4100000, '{(today + timedelta(days=1)).isoformat()}', 'E2E 미래', {uid})")
check("P4 미래 적용일 거부", not ok and "Future" in msg, msg)
s, sal = admin.call("GET", f"/employees/{eid}/salary-history")
check("P5 앱 급여 이력 API에도 같은 1건", s == 200 and sal.get("total") == 1, f"{s} {sal and sal.get('total')}")

# ---------------- sp_approve_step ----------------
a4 = emp04.me["user_id"]


def approval(title):
    s, d = emp03.call("POST", "/approvals", {"request_type": "GENERAL", "title": f"E2E 프로시저 {tag} {title}",
                                              "content": "프로시저 검사", "approver_user_ids": [uid, a4], "submit": True})
    if s == 201:
        made["approvals"].append(d["request_id"])
    return s, d


s, r1 = approval("승인")
check("S2 준비: 결재 상신(결재선 2명)", s == 201 and r1["status"] == "IN_PROGRESS", s)
rid = r1["request_id"]
ok, msg = call_proc(f"CALL sp_approve_step({rid}, 2, {a4}, 'APPROVED', 'E2E')")
check("R1 차례가 아닌 2단계 승인 거부", not ok and "not pending" in msg, msg)
ok, msg = call_proc(f"CALL sp_approve_step({rid}, 1, {a4}, 'APPROVED', 'E2E')")
check("R2 결재자가 아니면 거부", not ok and "approver mismatch" in msg, msg)
ok, msg = call_proc(f"CALL sp_approve_step({rid}, 1, {uid}, 'APPROVED', 'E2E 1단계')")
st, _ = mysql(f"SELECT CONCAT((SELECT status FROM approval_requests WHERE approval_request_id = {rid}), ',', "
              f"GROUP_CONCAT(status ORDER BY step_order)) FROM approval_steps WHERE approval_request_id = {rid}")
check("R3 1단계 승인 → 요청 진행 중, 다음 단계 PENDING", ok and st == "IN_PROGRESS,APPROVED,PENDING", msg or st)
ok, msg = call_proc(f"CALL sp_approve_step({rid}, 2, {a4}, 'APPROVED', 'E2E 2단계')")
s, d = emp03.call("GET", f"/approvals/{rid}")
check("R4 마지막 단계 승인 → 요청 APPROVED (앱 API로 확인)", ok and s == 200 and d["status"] == "APPROVED" and d.get("completed_at"),
      msg or f"{s} {d and d.get('status')}")
s, r2 = approval("반려")
rid2 = r2["request_id"]
ok, msg = call_proc(f"CALL sp_approve_step({rid2}, 1, {uid}, 'REJECTED', 'E2E 반려')")
st, _ = mysql(f"SELECT CONCAT((SELECT status FROM approval_requests WHERE approval_request_id = {rid2}), ',', "
              f"GROUP_CONCAT(status ORDER BY step_order)) FROM approval_steps WHERE approval_request_id = {rid2}")
check("R5 반려 → 요청 REJECTED, 남은 단계 SKIPPED", ok and st == "REJECTED,REJECTED,SKIPPED", msg or st)
ok, msg = call_proc(f"CALL sp_approve_step({rid2}, 2, {a4}, 'APPROVED', 'E2E')")
check("R6 끝난 결재는 거부", not ok and "not in progress" in msg, msg)

# ---------------- sp_delete_employee_without_assignment_history ----------------
ok, msg = call_proc(f"CALL sp_delete_employee_without_assignment_history({eid})")
check("D1 발령·급여 이력이 있으면 삭제 거부", not ok and "history" in msg, msg)
ok, msg = call_proc(f"CALL sp_delete_employee_without_assignment_history({eid2})")
left, _ = mysql(f"SELECT (SELECT COUNT(*) FROM employees WHERE employee_id = {eid2}) + (SELECT COUNT(*) FROM assignment_history WHERE employee_id = {eid2})")
check("D2 입사 이력만 있는 오등록 직원은 입사 이력과 함께 삭제", ok and left == "0", msg or left)
if ok:
    made["employees"].remove(eid2)

ok_n = sum(1 for _, c in results if c)
print(f"{ok_n}/{len(results)} passed")
sys.exit(0 if ok_n == len(results) else 1)
