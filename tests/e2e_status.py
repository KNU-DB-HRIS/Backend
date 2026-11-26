#!/usr/bin/env python3
"""재직 상태(휴직·복직)와 직급 필터 E2E (제안서 HR-03, HR-05, ORG-05)

usage: python3 e2e_status.py <api_base> <Backend dir>   (샘플 데이터 db-seed-demo 필요, 비밀번호는 출력하지 않음)
- 임시 직원 1명(계정 없음)을 만들어 검사한 뒤 지움
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


def code(js):
    return js.get("error", {}).get("code") if isinstance(js, dict) else None


def sql(q):
    return subprocess.run(["docker", "compose", "exec", "-T", "mysql", "sh", "-c",
                           f'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -N -e "{q}"'],
                          cwd=BDIR, capture_output=True, text=True).stdout.strip()


tag = uuid.uuid4().hex[:4]
made = []
admin = Client("admin01")


def cleanup():
    for eid in made:
        eid = int(eid)
        sql(f"DELETE FROM assignment_history WHERE employee_id = {eid}; DELETE FROM salary_history WHERE employee_id = {eid}; "
            f"DELETE FROM employees WHERE employee_id = {eid};")
    left = sql(f"SELECT COUNT(*) FROM employees WHERE email = 'status.{tag}@example.test'")
    print(f"cleanup: 임시 직원 남은 행 {left}")


atexit.register(cleanup)
today = date.today()
deps = {d["department_name"]: d["department_id"] for d in admin.call("GET", "/departments")[1]["items"]}
positions = admin.call("GET", "/positions")[1]["items"]
pos_a, pos_b = positions[0]["position_id"], positions[1]["position_id"]
job = admin.call("GET", "/jobs")[1]["items"][0]["job_id"]
s, e = admin.call("POST", "/employees", {
    "name": "상태검사", "email": f"status.{tag}@example.test", "phone": "010-5555-0004",
    "department_id": deps["개발팀"], "position_id": pos_a, "job_id": job,
    "hire_date": (today - timedelta(days=30)).isoformat(), "employment_type": "FULL_TIME"})
if s == 201:
    made.append(e["employee_id"])
check("S1 준비: 임시 직원 등록", s == 201, s)
eid = e["employee_id"]

# ---------------- 직급 필터 (HR-03, ORG-05) ----------------
s, js = admin.call("GET", f"/employees?position_id={pos_a}&size=100")
names = {x.get("position_name") for x in js["items"]}
check("P1 직급 필터: 그 직급 직원만, 새 직원 포함", s == 200 and len(names) == 1 and eid in {x["employee_id"] for x in js["items"]},
      f"{s} {names} n={js.get('total')}")
s, js = admin.call("GET", f"/employees?position_id={pos_b}&size=100")
check("P2 다른 직급이면 새 직원 없음", s == 200 and eid not in {x["employee_id"] for x in js["items"]}, s)
s, js = admin.call("GET", f"/employees?position_id={pos_a}&department_id={deps['개발팀']}&employment_status=ACTIVE&size=100")
check("P3 직급 + 부서 + 재직 상태 함께", s == 200 and eid in {x["employee_id"] for x in js["items"]}
      and all(x["department_name"] == "개발팀" for x in js["items"]), s)
s, js = admin.call("GET", "/employees?position_id=abc")
check("P4 직급 값이 숫자가 아니면 422", s == 422, f"{s} {code(js)}")

# ---------------- 휴직·복직 (HR-05) ----------------
base = {"effective_date": today.isoformat(), "reason": "E2E 상태 검사"}
s, js = admin.call("POST", f"/employees/{eid}/assignments", {**base, "action_type": "LEAVE", "to_department_id": deps["인사팀"]})
check("L1 휴직에 소속 변경을 함께 보내면 422", s == 422, f"{s} {code(js)}")
s, js = admin.call("POST", f"/employees/{eid}/assignments", {**base, "action_type": "LEAVE", "effective_date": (today + timedelta(days=3)).isoformat()})
check("L2 미래 휴직일 422 FUTURE_DATE_NOT_SUPPORTED", s == 422 and code(js) == "FUTURE_DATE_NOT_SUPPORTED", f"{s} {code(js)}")
s, js = admin.call("POST", f"/employees/{eid}/assignments", {**base, "action_type": "RETURN"})
check("L3 재직자 복직 409 INVALID_STATUS_TRANSITION", s == 409 and code(js) == "INVALID_STATUS_TRANSITION", f"{s} {code(js)}")
emp = Client("employee03")
s, js = emp.call("POST", f"/employees/{eid}/assignments", {**base, "action_type": "LEAVE"})
check("L4 사원은 휴직 처리 403", s == 403, f"{s} {code(js)}")
s, js = admin.call("POST", f"/employees/{eid}/assignments", {**base, "action_type": "LEAVE"})
check("L5 휴직 201: 재직 상태 ON_LEAVE, 소속 그대로, 이력 LEAVE",
      s == 201 and js["employee"]["employment_status"] == "ON_LEAVE" and js["employee"]["department_id"] == deps["개발팀"]
      and js["assignment"]["action_type"] == "LEAVE", s)
s, d = admin.call("GET", f"/employees/{eid}")
check("L6 직원 상세 재직 상태 ON_LEAVE", d.get("employment_status") == "ON_LEAVE", d.get("employment_status"))
s, js = admin.call("GET", "/employees?employment_status=ON_LEAVE&size=100")
check("L7 휴직 필터에 나옴", eid in {x["employee_id"] for x in js["items"]})
s, js = admin.call("POST", f"/employees/{eid}/assignments", {**base, "action_type": "LEAVE"})
check("L8 휴직자 다시 휴직 409", s == 409 and code(js) == "INVALID_STATUS_TRANSITION", f"{s} {code(js)}")
s, js = admin.call("POST", f"/employees/{eid}/assignments", {**base, "action_type": "RETURN"})
check("L9 복직 201: ACTIVE, 이력 RETURN", s == 201 and js["employee"]["employment_status"] == "ACTIVE"
      and js["assignment"]["action_type"] == "RETURN", s)
s, js = admin.call("GET", f"/employees/{eid}/assignments")
kinds = [x["action_type"] for x in js["items"]]
check("L10 발령 이력에 입사, 휴직, 복직", {"HIRE", "LEAVE", "RETURN"} <= set(kinds), kinds)
check("L11 DB: 휴직·복직 이력은 변경 전후 소속이 같음",
      sql(f"SELECT COUNT(*) FROM assignment_history WHERE employee_id = {eid} AND action_type IN ('LEAVE','RETURN') "
          f"AND from_department_id = to_department_id AND from_position_id = to_position_id") == "2")

ok = sum(1 for _, c in results if c)
print(f"{ok}/{len(results)} passed")
sys.exit(0 if ok == len(results) else 1)
