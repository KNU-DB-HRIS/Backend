#!/usr/bin/env python3
"""계열사(멀티 회사) 기능 E2E 테스트: 실제 백엔드 API를 HTTP로 호출해 검증 (비밀번호, 쿠키는 출력하지 않음)

usage: python3 e2e_multi_company.py <api_base e.g. http://127.0.0.1:18080/api/v1> <Backend dir (seed csv, docker compose)>
"""
import csv, json, subprocess, sys, urllib.error, urllib.request, http.cookiejar, uuid

API, BDIR = sys.argv[1].rstrip("/"), sys.argv[2]
CREDS = {r["username"]: r["password"] for r in csv.DictReader(open(f"{BDIR}/.seed-credentials.csv"))}
results = []


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = None

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(API + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.csrf and method != "GET":
            req.add_header("X-CSRF-Token", self.csrf)
        try:
            with self.op.open(req, timeout=40) as r:
                raw = r.read(); status = r.status
        except urllib.error.HTTPError as e:
            raw = e.read(); status = e.code
        try:
            js = json.loads(raw) if raw else None
        except Exception:
            js = None
        if isinstance(js, dict) and js.get("csrf_token"):
            self.csrf = js["csrf_token"]
        return status, js

    def login(self, user, password=None):
        pw = password or CREDS[user]
        s, _ = self.call("POST", "/auth/login", {"username": user, "password": pw})
        assert s == 200, f"login {user} -> {s}"
        me = self.call("GET", "/auth/me")[1]
        if me and me.get("password_change_required"):  # 임시 비밀번호 계정(024): 새 비밀번호부터 정함
            s, me = self.call("POST", "/auth/password", {"current_password": pw, "new_password": pw + "-n1"})
            assert s == 200, f"password change {user} -> {s}"
        return me


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def code(js):
    return (js or {}).get("error", {}).get("code") if isinstance(js, dict) else None


def sql(q):
    out = subprocess.run(["docker", "compose", "exec", "-T", "mysql", "sh", "-c",
                          f'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -N -e "{q}"'],
                         cwd=BDIR, capture_output=True, text=True)
    return out.stdout.strip()


tag = uuid.uuid4().hex[:4]
biz = f"{700 + int(tag[:2], 16) % 99:03d}-{int(tag[2:], 16) % 90 + 10:02d}-{int(tag, 16) % 90000 + 10000:05d}"

# T1 관리자 기본 상태
admin = Client(); me = admin.login("admin01")
home = me["company"]; hq_id = me["home_company_id"]
check("T1 /auth/me에 현재 회사와 회사 목록", home["company_id"] == hq_id and any(c["is_home"] for c in me["companies"]),
      f"{home['name']}, companies={len(me['companies'])}")
s, hq_emps = admin.call("GET", "/employees?page=1&size=100"); hq_total = hq_emps["total"]

# T2 계열사 생성: 검증, 중복, 정상
s, js = admin.call("POST", "/companies", {"name": "랩스", "business_number": "12-34"})
check("T2a 사업자번호 형식 오류 422", s == 422 and code(js) == "VALIDATION_ERROR", f"{s} {code(js)}")
hq_biz = admin.call("GET", "/company")[1]["business_number"]
s, js = admin.call("POST", "/companies", {"name": "랩스", "business_number": hq_biz})
check("T2b 사업자번호 중복 409", s == 409 and code(js) == "BUSINESS_NUMBER_DUPLICATE", f"{s} {code(js)}")
s, js = admin.call("POST", "/companies", {"name": f"샘플테크 랩스 {tag}", "business_number": biz, "ceo_name": "QA", "industry": "IT"})
check("T2c 계열사 생성 201", s == 201 and js.get("group_id"), f"{s} group={js and js.get('group_id')}")
labs_id = js["company_id"]
check("T2d 본사도 같은 그룹으로 묶임", sql(f"SELECT COUNT(DISTINCT group_id) FROM companies WHERE company_id IN ({hq_id},{labs_id})") == "1")
check("T2e 생성자에게 계열사 HR_ADMIN 부여(user_company_roles)",
      sql(f"SELECT COUNT(*) FROM user_company_roles ucr JOIN roles r ON r.role_id=ucr.role_id WHERE ucr.company_id={labs_id} AND r.role_code='HR_ADMIN'") == "1")

# T3 회사 전환
me = admin.call("GET", "/auth/me")[1]
check("T3a 전환 목록에 계열사 표시", any(c["company_id"] == labs_id for c in me["companies"]), f"{[c['name'] for c in me['companies']]}")
s, me = admin.call("POST", "/auth/active-company", {"company_id": labs_id})
check("T3b 계열사로 전환", s == 200 and me["company"]["company_id"] == labs_id and "HR_ADMIN" in me["roles"], f"{s} {me and me.get('company')}")
check("T3c 전환 후 GET /company = 계열사", admin.call("GET", "/company")[1]["company_id"] == labs_id)
me2 = admin.call("GET", "/auth/me")[1]
check("T3d 새 요청에도 전환 유지(세션 저장)", me2["company"]["company_id"] == labs_id)
check("T3e 전환이 감사 로그에 계열사로 기록", sql(f"SELECT COUNT(*) FROM audit_logs WHERE action_type='COMPANY_SWITCHED' AND company_id={labs_id}") != "0")

# T4 계열사 안에서 조직, 직원 만들기
s, emps = admin.call("GET", "/employees?page=1&size=100")
check("T4a 계열사 직원 목록은 비어 있음", s == 200 and emps["total"] == 0, f"total={emps and emps.get('total')}")
s, d = admin.call("POST", "/departments", {"department_name": "연구팀", "department_code": f"LAB{tag}"})
s2, p = admin.call("POST", "/positions", {"position_name": "연구원", "position_code": f"R{tag}", "level": 1})
s3, j = admin.call("POST", "/jobs", {"job_name": "연구개발", "job_code": f"RD{tag}", "job_family": "연구", "job_category": "R&D"})
check("T4b 계열사 부서, 직급, 직무 생성", (s, s2, s3) == (201, 201, 201), f"{s},{s2},{s3} {code(d) or ''}{code(p) or ''}{code(j) or ''}")
dep_id, pos_id, job_id = d.get("department_id"), p.get("position_id"), j.get("job_id")
s, e = admin.call("POST", "/employees", {"name": "랩스직원", "email": f"labs.{tag}@example.test", "phone": "010-7777-0000",
    "department_id": dep_id, "position_id": pos_id, "job_id": job_id, "hire_date": "2026-11-01",
    "employment_type": "FULL_TIME", "grant_access": True, "username": f"labs{tag}"})
check("T4c 계열사 직원 등록(접속 계정 포함)", s == 201, f"{s} {code(e)} {(e or {}).get('error', {}).get('details')}")
labs_emp = e.get("employee_id") if isinstance(e, dict) else None
labs_user, labs_pw = f"labs{tag}", (e or {}).get("temporary_password")
check("T4d 직원이 계열사 소속으로 저장", sql(f"SELECT company_id FROM employees WHERE employee_id={labs_emp}") == str(labs_id))

# T5 격리: 계열사 문맥에서 본사 데이터 안 보임
hq_emp_id = hq_emps["items"][1]["employee_id"]
s, js = admin.call("GET", f"/employees/{hq_emp_id}")
check("T5a 계열사 문맥에서 본사 직원 조회 404", s == 404, f"{s} {code(js)}")
s, js = admin.call("GET", "/search?q=" + urllib.request.quote(hq_emps["items"][1]["name"]))
check("T5b 통합 검색에 본사 직원 없음", s == 200 and not (js.get("employees") or {}).get("items"), f"{s}")
s, js = admin.call("GET", "/organization/headcounts?page=1&size=20")
check("T5c 조직 인원 집계는 계열사만", s == 200 and js["summary"]["total"] == 1, f"total={js and js.get('summary', {}).get('total')}")
s, js = admin.call("GET", "/dashboard")
check("T5d 대시보드 정상 응답", s == 200, f"{s}")

# T6 HR AI 범위
s, js = admin.call("POST", "/ai/queries", {"question": "재직 중인 직원은 몇 명이야?"})
val = (js or {}).get("rows", [[None]])[0][0] if isinstance(js, dict) and js.get("rows") else None
check("T6a 계열사 문맥 HR AI는 계열사 인원만", s == 200 and val == 1, f"{s} status={js and js.get('status')} value={val}")

# T7 결재는 소속 회사 기준 유지
s, js = admin.call("GET", "/approvals?tab=archive&page=1&size=10")
check("T7 계열사 문맥에서도 내 결재함(본사) 조회", s == 200 and js["total"] >= 1, f"{s} total={js and js.get('total')}")

# T8 본사로 복귀 후 계열사 데이터 안 보임
s, me = admin.call("POST", "/auth/active-company", {"company_id": hq_id})
check("T8a 본사로 복귀", s == 200 and me["company"]["company_id"] == hq_id)
s, js = admin.call("GET", "/employees?page=1&size=100")
check("T8b 본사 직원 수 그대로", js["total"] == hq_total, f"{js['total']} vs {hq_total}")
s, js = admin.call("GET", f"/employees/{labs_emp}")
check("T8c 본사 문맥에서 계열사 직원 404", s == 404, f"{s}")
s, js = admin.call("POST", "/ai/queries", {"question": "재직 중인 직원은 몇 명이야?"})
val = (js or {}).get("rows", [[None]])[0][0] if isinstance(js, dict) and js.get("rows") else None
check("T8d 본사 문맥 HR AI는 본사 인원", s == 200 and isinstance(val, int) and val > 1, f"value={val}")

# T9 권한 없는 전환
emp = Client(); me = emp.login("employee03")
check("T9a 본사 사원 목록엔 본사만", [c["company_id"] for c in me["companies"]] == [hq_id], f"{[c['name'] for c in me['companies']]}")
s, js = emp.call("POST", "/auth/active-company", {"company_id": labs_id})
check("T9b 본사 사원 → 계열사 전환 403", s == 403 and code(js) == "FORBIDDEN_SCOPE", f"{s} {code(js)}")
s, js = emp.call("POST", "/auth/active-company", {"company_id": 999999})
check("T9c 없는 회사 전환 403", s == 403, f"{s}")
s, js = emp.call("GET", "/companies")
check("T9d 사원은 계열사 목록 API 403", s == 403, f"{s}")
if labs_user and labs_pw:
    le = Client(); me = le.login(labs_user, labs_pw)
    check("T9e 계열사 직원 로그인: 현재 회사 = 계열사", me["company"]["company_id"] == labs_id and me["home_company_id"] == labs_id)
    s, js = le.call("POST", "/auth/active-company", {"company_id": hq_id})
    check("T9f 계열사 직원 → 본사 전환 403", s == 403, f"{s}")
else:
    check("T9e/f 계열사 직원 계정", False, f"username/temporary_password missing in response keys={list((e or {}).keys())}")

# T10 권한 회수 시 소속 회사로 되돌아감, 재로그인은 소속 회사에서 시작
admin.call("POST", "/auth/active-company", {"company_id": labs_id})
sql(f"DELETE FROM user_company_roles WHERE company_id={labs_id}")
me = admin.call("GET", "/auth/me")[1]
check("T10a 권한 회수 후 다음 요청은 소속 회사", me["company"]["company_id"] == hq_id and all(c["company_id"] != labs_id for c in me["companies"]))
role = sql("SELECT role_id FROM roles WHERE role_code='HR_ADMIN'")
uid = sql("SELECT user_id FROM users WHERE username='admin01'")
sql(f"INSERT INTO user_company_roles(user_id,company_id,role_id) VALUES({uid},{labs_id},{role})")
admin.call("POST", "/auth/active-company", {"company_id": labs_id})
admin.call("POST", "/auth/logout", {})
me = Client().login("admin01")
check("T10b 다시 로그인하면 소속 회사에서 시작", me["company"]["company_id"] == hq_id)

passed = sum(1 for _, ok, _ in results if ok)
print(f"\n{passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
