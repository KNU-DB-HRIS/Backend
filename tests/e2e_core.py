#!/usr/bin/env python3
"""제안서 기능 요구사항(HR-01~07, ORG-01~07) E2E: 검사 이름이 요구사항 ID와 같아 요구사항 추적표에서 바로 찾을 수 있음

usage: python3 e2e_core.py <api_base> <Backend dir>   (샘플 데이터 db-seed-demo 필요, 비밀번호는 출력하지 않음)
- 임시 직원, 부서, 직급을 만들어 검사하고 끝나면 모두 지움. 회사 정보는 바꾼 뒤 원래 값으로 되돌림
"""
import atexit, csv, json, subprocess, sys, urllib.error, urllib.parse, urllib.request, http.cookiejar, uuid
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


tag = uuid.uuid4().hex[:4].upper()
made = {"employees": [], "departments": [], "positions": []}
restore = {}
admin = Client("admin01")
today = date.today()


def cleanup():
    if "company" in restore:
        admin.call("PATCH", "/company", restore["company"])
    for eid in made["employees"]:
        eid = int(eid)
        sql(f"DELETE FROM salary_history WHERE employee_id = {eid}; DELETE FROM assignment_history WHERE employee_id = {eid}; "
            f"DELETE FROM employees WHERE employee_id = {eid};")
    for table, key in (("departments", "department_id"), ("positions", "position_id")):
        if made[table]:
            sql(f"DELETE FROM {table} WHERE {key} IN ({','.join(str(int(x)) for x in made[table])})")
    left = sql(f"SELECT (SELECT COUNT(*) FROM employees WHERE email LIKE 'core.%.{tag.lower()}@example.test') "
               f"+ (SELECT COUNT(*) FROM departments WHERE department_code LIKE 'E2E{tag}%') "
               f"+ (SELECT COUNT(*) FROM positions WHERE position_code LIKE 'E2E{tag}%')")
    print(f"cleanup: 임시 직원, 부서, 직급 남은 행 {left}")


atexit.register(cleanup)

# ---------------- 조직 (ORG-01~04, ORG-07) ----------------
s, co = admin.call("GET", "/company")
check("ORG-01a 회사 정보 조회", s == 200 and co.get("name") and co.get("business_number"), s)
restore["company"] = {"phone": co.get("phone")}
s, js = admin.call("PATCH", "/company", {"phone": "02-0000-" + "1234"})
s2, co2 = admin.call("GET", "/company")
check("ORG-01b 회사 정보 수정이 조회에 반영", s == 200 and co2.get("phone") == "02-0000-1234", f"{s} {code(js)}")
s, d = admin.call("POST", "/departments", {"department_name": f"검사부{tag}", "department_code": f"E2E{tag}D"})
if s == 201:
    made["departments"].append(d["department_id"])
s2, lst = admin.call("GET", "/departments")
check("ORG-02 부서 등록, 목록에 나옴", s == 201 and any(x["department_id"] == d["department_id"] for x in lst["items"]), f"{s} {code(d)}")
dep = d["department_id"]
s, js = admin.call("POST", "/departments", {"department_name": f"검사부{tag}2", "department_code": f"E2E{tag}D"})
check("ORG-02b 같은 회사 안 부서 코드 중복 409", s == 409, f"{s} {code(js)}")
s, js = admin.call("PATCH", f"/departments/{dep}", {"department_name": f"검사부{tag}수정"})
check("ORG-03a 부서 이름 수정", s == 200 and js.get("department_name") == f"검사부{tag}수정", f"{s} {code(js)}")
s, p = admin.call("POST", "/positions", {"position_name": f"검사직급{tag}", "position_code": f"E2E{tag}P", "level": 90 + int(tag[:1], 16) % 9})
if s == 201:
    made["positions"].append(p["position_id"])
s2, js = admin.call("PATCH", f"/positions/{p['position_id']}", {"position_name": f"검사직급{tag}수정"}) if s == 201 else (0, None)
check("ORG-04 직급 등록과 수정", s == 201 and s2 == 200, f"{s} {s2} {code(p)}")

# ---------------- 인사 (HR-01~07) ----------------
deps = {x["department_name"]: x["department_id"] for x in lst["items"]}
pos = admin.call("GET", "/positions")[1]["items"][0]["position_id"]
job = admin.call("GET", "/jobs")[1]["items"][0]["job_id"]


def new_employee(kind, department):
    return admin.call("POST", "/employees", {
        "name": f"요건{kind}", "email": f"core.{kind}.{tag.lower()}@example.test", "phone": "010-5555-0006",
        "department_id": department, "position_id": pos, "job_id": job,
        "hire_date": (today - timedelta(days=20)).isoformat(), "employment_type": "FULL_TIME"})


s, e = new_employee("a", dep)
if s == 201:
    made["employees"].append(e["employee_id"])
eid = e["employee_id"]
hist = sql(f"SELECT action_type FROM assignment_history WHERE employee_id = {eid}")
check("HR-01a 직원 등록 201: 사번 자동 부여(EMP), 입사 이력 기록", s == 201 and str(e.get("employee_no", "")).startswith("EMP") and hist == "HIRE",
      f"{s} {e.get('employee_no')} {hist}")
s, js = admin.call("POST", "/employees", {"name": "중복", "email": f"core.a.{tag.lower()}@example.test", "phone": "010-5555-0008", "department_id": dep,
                                          "position_id": pos, "job_id": job, "hire_date": today.isoformat(), "employment_type": "FULL_TIME"})
check("HR-01b 이메일 중복 409 (PR-03 입력 검증)", s == 409 and code(js) == "EMAIL_DUPLICATE", f"{s} {code(js)}")
s, js = admin.call("POST", "/employees", {"name": "없는부서", "email": f"core.x.{tag.lower()}@example.test", "phone": "010-5555-0009", "department_id": 999999,
                                          "position_id": pos, "job_id": job, "hire_date": today.isoformat(), "employment_type": "FULL_TIME"})
check("HR-01c 없는 부서 422 REFERENCE_INVALID (PR-03)", s == 422 and code(js) == "REFERENCE_INVALID", f"{s} {code(js)}")
s, js = admin.call("GET", "/employees?size=100")
check("HR-02 직원 목록: 사번, 이름, 부서, 직급, 재직 상태", s == 200 and js["total"] >= 1
      and {"employee_no", "name", "department_name", "position_name", "employment_status"} <= set(js["items"][0]), s)
s, js = admin.call("GET", "/employees?q=" + urllib.parse.quote(e["employee_no"]))
s2, js2 = admin.call("GET", "/employees?q=" + urllib.parse.quote(f"요건a"))
check("HR-03 사번, 이름으로 검색", s == s2 == 200 and [x["employee_id"] for x in js["items"]] == [eid]
      and eid in {x["employee_id"] for x in js2["items"]}, f"{s} {s2}")
s, d = admin.call("GET", f"/employees/{eid}")
s2, h = admin.call("GET", f"/employees/{eid}/assignments")
check("HR-04 직원 상세와 발령 이력(입사)", s == s2 == 200 and d["employee_no"] == e["employee_no"]
      and [x["action_type"] for x in h["items"]] == ["HIRE"], f"{s} {s2}")
s, js = admin.call("PATCH", f"/employees/{eid}", {"name": "요건a수정", "phone": "010-5555-0007"})
s2, d = admin.call("GET", f"/employees/{eid}")
check("HR-05 기본 정보 수정이 상세에 반영", s == 200 and d["name"] == "요건a수정" and d["phone"] == "010-5555-0007", f"{s} {code(js)}")
s, js = admin.call("POST", f"/employees/{eid}/assignments", {"action_type": "TRANSFER", "effective_date": today.isoformat(),
                                                           "reason": "E2E 요건", "to_department_id": deps["개발팀"]})
s2, d = admin.call("GET", f"/employees/{eid}")
row = sql(f"SELECT CONCAT(from_department_id, '>', to_department_id) FROM assignment_history WHERE employee_id = {eid} AND action_type = 'TRANSFER'")
check("HR-06 인사 발령: 이력(변경 전후)과 현재 소속을 함께 갱신", s == 201 and d["department_id"] == deps["개발팀"] and row == f"{dep}>{deps['개발팀']}",
      f"{s} {code(js)} {row}")
s, js = admin.call("DELETE", f"/employees/{eid}")
check("HR-07a 발령 이력이 있는 직원 삭제 409, 기록 유지", s == 409 and code(js) == "EMPLOYEE_HAS_HISTORY", f"{s} {code(js)}")
s, e2 = new_employee("b", deps["개발팀"])
if s == 201:
    made["employees"].append(e2["employee_id"])
s, js = admin.call("DELETE", f"/employees/{e2['employee_id']}")
left = sql(f"SELECT COUNT(*) FROM employees WHERE employee_id = {int(e2['employee_id'])}")
check("HR-07b 이력 없는 오등록 직원 삭제 204", s == 204 and left == "0", f"{s} {left}")
if s == 204:
    made["employees"].remove(e2["employee_id"])

# ---------------- 조직별 조회·집계, 삭제(사용 중지) (ORG-05~07) ----------------
s, js = admin.call("GET", f"/employees?department_id={deps['개발팀']}&position_id={pos}&size=100")
check("ORG-05 부서·직급으로 직원 조회", s == 200 and eid in {x["employee_id"] for x in js["items"]}
      and all(x["department_name"] == "개발팀" for x in js["items"]), s)
s, hc = admin.call("GET", "/organization/headcounts?size=100")
dev = next((x for x in hc["items"] if x["department_id"] == deps["개발팀"]), {})
db_total = sql(f"SELECT COUNT(*) FROM employees WHERE department_id = {deps['개발팀']} AND employment_status IN ('ACTIVE','ON_LEAVE')")
check("ORG-06a 부서별 인원 집계 = DB 재직·휴직 인원", s == 200 and str(dev.get("total")) == db_total, f"{dev.get('total')} vs {db_total}")
s, pl = admin.call("GET", "/positions")
p0 = next(x for x in pl["items"] if x["position_id"] == pos)
db_pos = sql(f"SELECT COUNT(*) FROM employees WHERE position_id = {pos} AND employment_status IN ('ACTIVE','ON_LEAVE') "
             f"AND company_id = (SELECT company_id FROM positions WHERE position_id = {pos})")
check("ORG-06b 직급별 인원 = DB", str(p0.get("headcount")) == db_pos, f"{p0.get('headcount')} vs {db_pos}")
s, js = admin.call("DELETE", f"/departments/{deps['개발팀']}")
check("ORG-07a 소속 인원이 있는 부서 사용 중지 409", s == 409 and code(js) == "DEPARTMENT_IN_USE", f"{s} {code(js)}")
s, js = admin.call("DELETE", f"/departments/{dep}")
s2, d = admin.call("GET", f"/departments/{dep}")
check("ORG-07b 빈 부서 사용 중지 204, 행은 남고 is_active=false", s == 204 and s2 == 200 and d["is_active"] is False, f"{s} {s2}")
s, js = new_employee("c", dep)
if s == 201:
    made["employees"].append(js["employee_id"])
check("ORG-03b 사용 중지 부서에는 신규 배정 불가 422", s == 422, f"{s} {code(js)}")

ok = sum(1 for _, c in results if c)
print(f"{ok}/{len(results)} passed")
sys.exit(0 if ok == len(results) else 1)
