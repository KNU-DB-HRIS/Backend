#!/usr/bin/env python3
"""첫 로그인 비밀번호 변경, 관리자 비밀번호 초기화 E2E (024)

usage: python3 e2e_password.py <api_base> <Backend dir>   (샘플 데이터 db-seed-demo 필요, 비밀번호는 출력하지 않음)
- 임시 직원 1명(계정 포함)을 만들어 검사한 뒤 지움. 샘플 계정 비밀번호는 바꾸지 않음
"""
import atexit, csv, json, subprocess, sys, urllib.error, urllib.request, http.cookiejar, uuid
from datetime import date

API, BDIR = sys.argv[1].rstrip("/"), sys.argv[2]
CREDS = {r["username"]: r["password"] for r in csv.DictReader(open(f"{BDIR}/.seed-credentials.csv", encoding="utf-8"))}
results = []


class Client:
    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = None

    def call(self, method, path, body=None):
        req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, method=method)
        req.add_header("Content-Type", "application/json")
        if self.csrf and method != "GET":
            req.add_header("X-CSRF-Token", self.csrf)
        try:
            with self.op.open(req, timeout=60) as r:
                raw, status = r.read(), r.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        try:
            js = json.loads(raw) if raw and raw[:1] in (b"{", b"[") else None
        except Exception:
            js = None
        if isinstance(js, dict) and js.get("csrf_token"):
            self.csrf = js["csrf_token"]
        return status, js

    def login(self, user, password):
        return self.call("POST", "/auth/login", {"username": user, "password": password})


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail != "" else ""))


def code(js):
    return js.get("error", {}).get("code") if isinstance(js, dict) else None


def sql(q):
    return subprocess.run(["docker", "compose", "exec", "-T", "mysql", "sh", "-c",
                           f'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -N -e "{q}"'],
                          cwd=BDIR, capture_output=True, text=True).stdout.strip()


tag = uuid.uuid4().hex[:4]
made = []
admin = Client()
admin.login("admin01", CREDS["admin01"])


def cleanup():
    for eid in made:
        eid = int(eid)
        sql(" ".join([
            f"SET @e = {eid}; SET @u = (SELECT user_id FROM users WHERE employee_id = @e LIMIT 1);",
            "DELETE FROM auth_sessions WHERE user_id = @u; DELETE FROM user_company_roles WHERE user_id = @u;",
            "DELETE FROM user_roles WHERE user_id = @u;",
            "DELETE FROM audit_logs WHERE user_id = @u OR (action_type = 'PASSWORD_RESET' AND resource_id = @u);",
            "DELETE FROM users WHERE user_id = @u;",
            "DELETE FROM salary_history WHERE employee_id = @e; DELETE FROM assignment_history WHERE employee_id = @e;",
            "DELETE FROM employees WHERE employee_id = @e;",
        ]))
    left = sql(f"SELECT (SELECT COUNT(*) FROM employees WHERE email = 'pw.{tag}@example.test') "
               f"+ (SELECT COUNT(*) FROM users WHERE username = 'pw{tag}')")
    print(f"cleanup: 임시 직원, 계정 남은 행 {left}")


atexit.register(cleanup)

# ---------------- 1. 직원 등록(계정 발급) → 첫 로그인은 비밀번호 변경부터 ----------------
deps = {d["department_name"]: d["department_id"] for d in admin.call("GET", "/departments")[1]["items"]}
pos = admin.call("GET", "/positions")[1]["items"][0]["position_id"]
job = admin.call("GET", "/jobs")[1]["items"][0]["job_id"]
user = f"pw{tag}"
s, e = admin.call("POST", "/employees", {
    "name": "비번검사", "email": f"pw.{tag}@example.test", "phone": "010-5555-0002",
    "department_id": deps["개발팀"], "position_id": pos, "job_id": job, "hire_date": date.today().isoformat(),
    "employment_type": "FULL_TIME", "grant_access": True, "username": user})
if s == 201:
    made.append(e["employee_id"])
temp = (e or {}).get("temporary_password")
check("S1 준비: 직원 등록 + 계정 발급(임시 비밀번호)", s == 201 and temp, s)
eid = e["employee_id"]
s, d = admin.call("GET", f"/employees/{eid}")
check("A1 직원 상세 계정에 '비밀번호 변경 필요' 표시", s == 200 and d["account"]["password_change_required"] is True, d and d.get("account"))

u = Client()
s, js = u.login(user, temp)
check("F1 임시 비밀번호 로그인 200, 응답에 password_change_required=true", s == 200 and js.get("password_change_required") is True, s)
s, me = u.call("GET", "/auth/me")
check("F2 /auth/me 허용, password_change_required=true", s == 200 and me.get("password_change_required") is True, s)
blocked = {p: u.call("GET", p) for p in ("/me/events", "/approvals/summary", "/search?q=a")}
check("F3 다른 API는 403 PASSWORD_CHANGE_REQUIRED", all(st == 403 and code(j) == "PASSWORD_CHANGE_REQUIRED" for st, j in blocked.values()),
      {p: (st, code(j)) for p, (st, j) in blocked.items()})
s, js = u.call("POST", "/auth/password", {"current_password": "wrong-password-123", "new_password": "Brand-new-pass-2026"})
check("F4 지금 비밀번호 틀림 422 CURRENT_PASSWORD_INVALID", s == 422 and code(js) == "CURRENT_PASSWORD_INVALID", f"{s} {code(js)}")
s, js = u.call("POST", "/auth/password", {"current_password": temp, "new_password": "short1"})
check("F5 12자 미만 422 PASSWORD_POLICY", s == 422 and code(js) == "PASSWORD_POLICY", f"{s} {code(js)}")
s, js = u.call("POST", "/auth/password", {"current_password": temp, "new_password": f"{user}-is-my-pass"})
check("F6 아이디 포함 422 PASSWORD_POLICY", s == 422 and code(js) == "PASSWORD_POLICY", f"{s} {code(js)}")
s, js = u.call("POST", "/auth/password", {"current_password": temp, "new_password": temp})
check("F7 같은 비밀번호 422 PASSWORD_REUSED", s == 422 and code(js) == "PASSWORD_REUSED", f"{s} {code(js)}")

other = Client()
other.login(user, temp)
new_pw = "Brand-new-pass-2026-" + tag
s, js = u.call("POST", "/auth/password", {"current_password": temp, "new_password": new_pw})
check("F8 변경 200, 세션 응답 password_change_required=false, CSRF 재발급", s == 200 and js.get("password_change_required") is False and js.get("csrf_token"), s)
s, _ = u.call("GET", "/me/events")
check("F9 변경 뒤 같은 세션으로 다른 API 사용", s == 200, s)
s, _ = other.call("GET", "/auth/me")
check("F10 내 다른 세션은 끊김(401)", s == 401, s)
s, _ = Client().login(user, temp)
s2, js2 = Client().login(user, new_pw)
check("F11 예전 임시 비밀번호 401, 새 비밀번호 200(변경 필요 없음)", s == 401 and s2 == 200 and js2.get("password_change_required") is False, f"{s} {s2}")
check("F12 DB: password_change_required=0, password_changed_at 기록",
      sql(f"SELECT CONCAT(password_change_required, IF(password_changed_at IS NULL, 'n', 'y')) FROM users WHERE username='{user}'") == "0y")
s, js = u.call("POST", "/auth/password", {"current_password": new_pw, "new_password": "Second-change-pass-" + tag})
check("F13 일반 상태에서도 스스로 변경 가능", s == 200 and js.get("password_change_required") is False, s)
new_pw = "Second-change-pass-" + tag

# ---------------- 2. 관리자 비밀번호 초기화 ----------------
emp = Client()
emp.login("employee03", CREDS["employee03"])
s, js = emp.call("POST", f"/employees/{eid}/password-reset", {})
check("R1 사원은 초기화 403", s == 403, f"{s} {code(js)}")
s, js = admin.call("POST", f"/employees/{admin.call('GET', '/auth/me')[1]['employee_id']}/password-reset", {})
check("R2 관리자 본인 초기화 409 SELF_PASSWORD_RESET", s == 409 and code(js) == "SELF_PASSWORD_RESET", f"{s} {code(js)}")
s, js = admin.call("POST", f"/employees/{eid}/password-reset", {})
temp2 = (js or {}).get("temporary_password")
check("R3 관리자 초기화 200, 새 임시 비밀번호 한 번 반환", s == 200 and temp2 and temp2 != temp and js.get("username") == user, s)
s, _ = u.call("GET", "/auth/me")
check("R4 초기화하면 그 계정의 세션 모두 끊김", s == 401, s)
s, _ = Client().login(user, new_pw)
s2, js2 = Client().login(user, temp2)
check("R5 이전 비밀번호 401, 임시 비밀번호 로그인은 다시 변경 필요", s == 401 and s2 == 200 and js2.get("password_change_required") is True, f"{s} {s2}")
s, d = admin.call("GET", f"/employees/{eid}")
check("R6 직원 상세에 '비밀번호 변경 필요' 다시 표시", d["account"]["password_change_required"] is True)
check("R7 감사 기록: PASSWORD_CHANGED 2, PASSWORD_RESET 1",
      sql(f"SELECT CONCAT(SUM(action_type='PASSWORD_CHANGED'), SUM(action_type='PASSWORD_RESET')) FROM audit_logs "
          f"WHERE resource_type='user' AND resource_id=(SELECT user_id FROM users WHERE username='{user}')") == "21")
s, js = admin.call("POST", "/employees/999999/password-reset", {})
check("R8 없는 직원 404", s == 404, f"{s} {code(js)}")

ok = sum(1 for _, c in results if c)
print(f"{ok}/{len(results)} passed")
sys.exit(0 if ok == len(results) else 1)
