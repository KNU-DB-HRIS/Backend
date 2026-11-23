#!/usr/bin/env python3
"""역할별 권한 E2E: HR 관리자 / 인사 담당자 / 인사 사원 / 사원이 API마다 허용·거부되는지 실제 API로 검증

usage: python3 e2e_roles.py <api_base> <Backend dir>   (샘플 데이터 db-seed-demo 필요, 비밀번호는 출력하지 않음)
- 임시 직원 2명(인사팀)을 만들어 인사 담당자, 인사 사원 역할을 주고 검사한 뒤 지움
- 바꾸는 요청은 본문을 일부러 틀리게 보냄: 권한이 있으면 422(검증), 없으면 403. 데이터가 바뀌지 않음
- DB의 role_permissions가 app/permissions.py 표와 같은지도 대조
"""
import atexit, csv, importlib.util, json, subprocess, sys, urllib.error, urllib.parse, urllib.request, http.cookiejar, uuid
from datetime import date
from pathlib import Path

API, BDIR = sys.argv[1].rstrip("/"), sys.argv[2]
CREDS = {r["username"]: r["password"] for r in csv.DictReader(open(f"{BDIR}/.seed-credentials.csv", encoding="utf-8"))}
spec = importlib.util.spec_from_file_location("permissions", Path(BDIR) / "app" / "permissions.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
results = []


class Client:
    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = None
        self.me = None

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

    def login(self, user, password=None):
        s, _ = self.call("POST", "/auth/login", {"username": user, "password": password or CREDS[user]})
        assert s == 200, f"login {user} -> {s}"
        self.me = self.call("GET", "/auth/me")[1]
        return self


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
made = {"employees": [], "documents": []}
admin = Client().login("admin01")
emp = Client().login("employee03")


def cleanup():
    """만든 문서(행과 PDF), 임시 직원과 계정을 지움. 중간에 실패해도 실행"""
    if made["documents"]:
        ids = ",".join(str(int(x)) for x in made["documents"])
        for path in sql(f"SELECT file_path FROM documents WHERE document_id IN ({ids})").split():
            subprocess.run(["docker", "compose", "exec", "-T", "backend", "sh", "-c", f'rm -f "$STORAGE_DIR/{path}"'],
                           cwd=BDIR, capture_output=True)
        sql(f"DELETE FROM documents WHERE document_id IN ({ids})")
    for eid in made["employees"]:
        eid = int(eid)
        sql(" ".join([
            f"SET @e = {eid}; SET @u = (SELECT user_id FROM users WHERE employee_id = @e LIMIT 1);",
            "DELETE FROM auth_sessions WHERE user_id = @u; DELETE FROM user_company_roles WHERE user_id = @u;",
            "DELETE FROM user_roles WHERE user_id = @u; DELETE FROM audit_logs WHERE user_id = @u OR (action_type = 'ROLE_CHANGED' AND resource_id = @u);",
            "DELETE FROM users WHERE user_id = @u;",
            "DELETE FROM salary_history WHERE employee_id = @e; DELETE FROM assignment_history WHERE employee_id = @e;",
            "DELETE FROM employees WHERE employee_id = @e;",
        ]))
    left = sql(f"SELECT (SELECT COUNT(*) FROM employees WHERE email LIKE 'role.%.{tag}@example.test') "
               f"+ (SELECT COUNT(*) FROM users WHERE username LIKE 'role%{tag}')")
    print(f"cleanup: 임시 직원, 계정 남은 행 {left}")


atexit.register(cleanup)

# ---------------- 0. DB 권한 표 = app/permissions.py ----------------
rows = sql("SELECT r.role_code, p.permission_code FROM role_permissions rp JOIN roles r ON r.role_id = rp.role_id "
           "JOIN permissions p ON p.permission_id = rp.permission_id WHERE r.is_active = 1 AND p.is_active = 1").splitlines()
db = {}
for line in rows:
    role, perm = line.split("\t")
    db.setdefault(role, set()).add(perm)
diff = {r: sorted(db.get(r, set()) ^ P.GRANTS[r]) for r in P.GRANTS if db.get(r, set()) != P.GRANTS[r]}
check("P0 DB role_permissions = app/permissions.py 표 (역할 4개)", not diff, diff or {r: len(v) for r, v in P.GRANTS.items()})

# ---------------- 1. 임시 직원 2명 + 역할 부여 ----------------
deps = {d["department_name"]: d["department_id"] for d in admin.call("GET", "/departments")[1]["items"]}
pos = admin.call("GET", "/positions")[1]["items"][0]["position_id"]
job = admin.call("GET", "/jobs")[1]["items"][0]["job_id"]
accounts = {}
for kind in ("manager", "staff"):
    s, e = admin.call("POST", "/employees", {
        "name": f"역할검사{kind[0].upper()}", "email": f"role.{kind}.{tag}@example.test", "phone": "010-5555-0001",
        "department_id": deps["인사팀"], "position_id": pos, "job_id": job, "hire_date": date.today().isoformat(),
        "employment_type": "FULL_TIME", "grant_access": True, "username": f"role{kind[0]}{tag}"})
    if s == 201:
        made["employees"].append(e["employee_id"])
    accounts[kind] = e
check("S1 준비: 인사팀 임시 직원 2명(계정 포함)", all((accounts[k] or {}).get("temporary_password") for k in accounts),
      [accounts[k] and accounts[k].get("employee_id") for k in accounts])
mid, sid = accounts["manager"]["employee_id"], accounts["staff"]["employee_id"]

s1, j1 = admin.call("PUT", f"/employees/{mid}/role", {"role_code": "HR_MANAGER"})
s2, j2 = admin.call("PUT", f"/employees/{sid}/role", {"role_code": "HR_STAFF"})
check("R1 관리자가 역할 부여: 인사 담당자, 인사 사원", s1 == s2 == 200 and j1["role_code"] == "HR_MANAGER" and j2["role_name"] == "인사 사원",
      f"{s1} {s2} {j2 and j2.get('role_name')}")
s, d = admin.call("GET", f"/employees/{sid}")
check("R2 직원 상세의 계정에 현재 역할", s == 200 and d["account"]["role_code"] == "HR_STAFF" and d["account"]["role_name"] == "인사 사원",
      d and d.get("account"))
s, js = admin.call("PUT", f"/employees/{sid}/role", {"role_code": "HR_STAFF"})
check("R3 같은 역할로 다시 → 422 NO_CHANGE", s == 422 and code(js) == "NO_CHANGE", f"{s} {code(js)}")
s, js = admin.call("PUT", f"/employees/{sid}/role", {"role_code": "SUPER"})
check("R4 없는 역할 → 422", s == 422, s)
s, js = admin.call("PUT", f"/employees/{admin.me['employee_id']}/role", {"role_code": "EMPLOYEE"})
check("R5 본인 역할 변경 → 409 SELF_ROLE_CHANGE (관리자가 스스로 권한을 잃지 않게)", s == 409 and code(js) == "SELF_ROLE_CHANGE", f"{s} {code(js)}")

mgr = Client().login(f"rolem{tag}", accounts["manager"]["temporary_password"])
stf = Client().login(f"roles{tag}", accounts["staff"]["temporary_password"])
for label, c, role in (("관리자", admin, "HR_ADMIN"), ("인사 담당자", mgr, "HR_MANAGER"), ("인사 사원", stf, "HR_STAFF"), ("사원", emp, "EMPLOYEE")):
    want_menus = {m[5:] for m in P.GRANTS[role] if m.startswith("MENU_")}
    want_perms = {x for x in P.GRANTS[role] if not x.startswith("MENU_")}
    me = c.me
    check(f"M {label}: /auth/me 역할, 메뉴 {len(want_menus)}개, 권한 {len(want_perms)}개",
          me["role"] == role and set(me["menus"]) == want_menus and set(me["permissions"]) == want_perms,
          f"{me['role']} {me['role_label']} menus={len(me['menus'])} perms={len(me['permissions'])}")

# ---------------- 2. API별 허용(403 아님) / 거부(403) ----------------
other = next(x["employee_id"] for x in admin.call("GET", "/employees?page=1&size=20")[1]["items"]
             if x["employee_id"] not in (mid, sid, admin.me["employee_id"]) and x["employment_status"] == "ACTIVE")
BAD = {"email": "not-an-email"}
CASES = [  # (설명, method, path, body, 이 권한이 있어야 허용)
    ("회사 대시보드", "GET", "/dashboard", None, "DASHBOARD_COMPANY"),
    ("회사 일정 전체", "GET", "/events", None, "EVENT_MANAGE"),
    ("일정 등록", "POST", "/events", {}, "EVENT_MANAGE"),
    ("직원 목록", "GET", "/employees?page=1&size=5", None, "EMPLOYEE_READ"),
    ("다른 직원 상세", "GET", f"/employees/{other}", None, "EMPLOYEE_READ"),
    ("다른 직원 발령 이력", "GET", f"/employees/{other}/assignments", None, "EMPLOYEE_READ"),
    ("직원 등록", "POST", "/employees", {}, "EMPLOYEE_CREATE"),
    ("기본 정보 수정", "PATCH", f"/employees/{other}", BAD, "EMPLOYEE_UPDATE"),
    ("인사 발령", "POST", f"/employees/{other}/assignments", {}, "EMPLOYEE_ASSIGN"),
    ("퇴사 처리", "POST", f"/employees/{other}/termination", {}, "EMPLOYEE_TERMINATE"),
    ("직원 삭제", "DELETE", "/employees/2147483000", None, "EMPLOYEE_DELETE"),
    ("역할 변경", "PUT", f"/employees/{other}/role", {}, "ROLE_MANAGE"),
    ("급여 목록", "GET", "/salaries?page=1&size=5", None, "SALARY_READ"),
    ("다른 직원 현재 급여", "GET", f"/employees/{other}/salary", None, "SALARY_READ"),
    ("다른 직원 급여 이력", "GET", f"/employees/{other}/salary-history", None, "SALARY_READ"),
    ("급여 변경 등록", "POST", f"/employees/{other}/salary-history", {}, "SALARY_UPDATE"),
    ("회사 정보", "GET", "/company", None, "ORG_READ"),
    ("부서 목록", "GET", "/departments", None, "ORG_READ"),
    ("조직 인원 집계", "GET", "/organization/headcounts?page=1&size=5", None, "ORG_READ"),
    ("부서 등록", "POST", "/departments", {}, "ORG_MANAGE"),
    ("회사 정보 수정", "PATCH", "/company", {"company_name": ""}, "ORG_MANAGE"),
    ("계열사 목록", "GET", "/companies", None, "COMPANY_MANAGE"),
    ("계열사 등록", "POST", "/companies", {}, "COMPANY_MANAGE"),
    ("평가 회차", "GET", "/evaluation-periods", None, "EVALUATION_READ"),
    ("HR AI", "POST", "/ai/queries", {}, "AI_QUERY"),
]
for label, c, role in (("관리자", admin, "HR_ADMIN"), ("인사 담당자", mgr, "HR_MANAGER"), ("인사 사원", stf, "HR_STAFF"), ("사원", emp, "EMPLOYEE")):
    wrong = []
    for desc, method, path, body, perm in CASES:
        s, js = c.call(method, path, body)
        allowed = perm in P.GRANTS[role]
        if (s == 403) == allowed or s >= 500 or s == 401:
            wrong.append(f"{desc}:{s}")
    check(f"A {label}: API {len(CASES)}개 허용·거부가 권한표대로", not wrong, wrong or "ok")

# 본인 급여는 누구나
s, _ = stf.call("GET", f"/employees/{sid}/salary")
check("A2 인사 사원도 본인 급여 조회는 403 아님", s != 403, s)

# ---------------- 3. 결재: 전체 조회 권한 ----------------
Q = "/approvals?tab=archive&status=APPROVED&page=1&size=1"  # 기본 탭(내가 결재할 문서)이 아니라 완료 문서함
ta = admin.call("GET", Q)[1]["total"]
tm = mgr.call("GET", Q)[1]["total"]
ts = stf.call("GET", Q)[1]["total"]
check("B1 승인 완료 문서: 인사 담당자는 회사 전체(관리자와 같은 수), 인사 사원은 본인 관련만(0건)", ta > 0 and tm == ta and ts == 0, f"admin={ta} manager={tm} staff={ts}")
some = admin.call("GET", Q)[1]["items"][0]["request_id"]
check("B2 인사 사원이 남의 결재 상세 → 403", stf.call("GET", f"/approvals/{some}")[0] == 403)

# ---------------- 4. 증명서: 대리 발급, 급여 문서 격리 ----------------
s, js = stf.call("POST", "/certificates", {"employee_id": other, "certificate_type": "EMPLOYMENT"})
if s == 201:
    made["documents"].append(js["document_id"])
check("C1 인사 사원: 다른 직원 재직증명서 대리 발급 201", s == 201, s)
s, js = emp.call("POST", "/certificates", {"employee_id": other, "certificate_type": "EMPLOYMENT"})
check("C2 사원: 다른 직원 증명서 → 403 FORBIDDEN_SCOPE", s == 403 and code(js) == "FORBIDDEN_SCOPE", f"{s} {code(js)}")
row = sql(f"SELECT employee_id, pay_month FROM payroll_statements WHERE status IN ('CONFIRMED','PAID') AND employee_id <> {sid} "
          "ORDER BY pay_month DESC LIMIT 1").split("\t")
pay_emp, pay_month = int(row[0]), row[1]
s, js = stf.call("POST", "/certificates/payslip", {"employee_id": pay_emp, "pay_month": pay_month})
check("C3 인사 사원: 다른 직원 급여명세서 → 403 FORBIDDEN_SCOPE", s == 403 and code(js) == "FORBIDDEN_SCOPE", f"{s} {code(js)}")
s, js = mgr.call("POST", "/certificates/payslip", {"employee_id": pay_emp, "pay_month": pay_month})
if s == 201:
    made["documents"].append(js["document_id"])
check("C4 인사 담당자: 다른 직원 급여명세서 201", s == 201, f"{s} {code(js)}")
slip = js.get("document_id") if s == 201 else None
s, lst = stf.call("GET", f"/documents?employee_id={pay_emp}&page=1&size=100")
kinds = {x["document_type"] for x in (lst or {}).get("items", [])}
mkinds = {x["document_type"] for x in (mgr.call("GET", f"/documents?employee_id={pay_emp}&page=1&size=100")[1] or {}).get("items", [])}
check("C5 발급 내역: 인사 담당자에게는 보이는 남의 급여명세서가 인사 사원에게는 안 보임",
      s == 200 and "PAYSLIP" in mkinds and not kinds & {"PAYSLIP", "WITHHOLDING"}, f"{s} manager={sorted(mkinds)} staff={sorted(kinds)}")
if slip:
    check("C6 인사 사원이 남의 급여명세서 파일 → 403, 인사 담당자는 200",
          stf.call("GET", f"/documents/{slip}/file")[0] == 403 and mgr.call("GET", f"/documents/{slip}/file")[0] == 200)

# ---------------- 5. 검색: 인사 역할은 관리자 수준 ----------------
for label, c, full in (("인사 사원", stf, True), ("사원", emp, False)):
    s, js = c.call("GET", "/search?q=" + urllib.parse.quote("개발"))
    items = (js or {}).get("employees", {}).get("items", [])
    check(f"Q {label}: 구성원 검색 {'관리자 수준(재직 상태 포함)' if full else '주소록 수준'}",
          s == 200 and items and (("employment_status" in items[0]) == full), f"{s} n={len(items)}")

# ---------------- 6. 역할을 바꾸면 다음 요청부터 바로 적용 ----------------
s, _ = admin.call("PUT", f"/employees/{sid}/role", {"role_code": "EMPLOYEE"})
s2, me = stf.call("GET", "/auth/me")
s3, _ = stf.call("GET", "/employees?page=1&size=1")
check("R6 인사 사원 → 사원으로 바꾸면 같은 세션에서 바로 메뉴 4개, 직원 목록 403",
      s == 200 and s2 == 200 and me["role"] == "EMPLOYEE" and len(me["menus"]) == 4 and s3 == 403, f"{s} {me and me.get('menus')} {s3}")
audit_n = sql(f"SELECT COUNT(*) FROM audit_logs WHERE action_type = 'ROLE_CHANGED' AND resource_id = "
              f"(SELECT user_id FROM users WHERE employee_id = {sid})")
check("R7 역할 변경은 감사 기록 ROLE_CHANGED (부여 1 + 되돌림 1, 거부된 요청은 기록 없음)", audit_n == "2", audit_n)

passed = sum(ok for _, ok in results)
print(f"\n{passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
