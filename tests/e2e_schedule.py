#!/usr/bin/env python3
"""일정 관리 E2E: 표시 대상 조직(전사, 지정 조직, 하위 포함) 등록, 수정, 삭제와 사원별 표시를 실제 API로 검증

usage: python3 e2e_schedule.py <api_base> <Backend dir>   (샘플 데이터 db-seed-demo 필요, 비밀번호는 출력하지 않음)
"""
import csv, json, os, subprocess, sys, urllib.error, urllib.request, http.cookiejar, uuid
from datetime import date, timedelta

API, BDIR = sys.argv[1].rstrip("/"), sys.argv[2]
CREDS = {r["username"]: r["password"] for r in csv.DictReader(open(f"{BDIR}/.seed-credentials.csv"))}
MEDIA = f"{BDIR}/.seed-credentials-media.csv"
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
            with self.op.open(req, timeout=40) as r:
                raw, status = r.read(), r.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        try:
            js = json.loads(raw) if raw else None
        except Exception:
            js = None
        if isinstance(js, dict) and js.get("csrf_token"):
            self.csrf = js["csrf_token"]
        return status, js

    def login(self, user, password=None):
        s, _ = self.call("POST", "/auth/login", {"username": user, "password": password or CREDS[user]})
        assert s == 200, f"login {user} -> {s}"
        return self.call("GET", "/auth/me")[1]


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def code(js):
    return js.get("error", {}).get("code") if isinstance(js, dict) else None


def field(js):
    return (js.get("error", {}).get("details") or {}).get("field") if isinstance(js, dict) else None


def sql(q):
    return subprocess.run(["docker", "compose", "exec", "-T", "mysql", "sh", "-c",
                           f'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -N -e "{q}"'],
                          cwd=BDIR, capture_output=True, text=True).stdout.strip()


def my_ids(client):
    s, js = client.call("GET", "/me/events?page=1&size=100")
    return {e["event_id"] for e in (js or {}).get("items", [])}


tag = uuid.uuid4().hex[:4]
day = (date.today() + timedelta(days=3)).isoformat()
admin = Client(); me = admin.login("admin01")
check("S0 메뉴에 일정(SCHEDULE) 포함", "SCHEDULE" in me["menus"], f"{me['menus']}")
deps = {d["department_name"]: d for d in admin.call("GET", "/departments")[1]["items"]}
dev, design = deps["개발팀"]["department_id"], deps["디자인팀"]["department_id"]
pos = admin.call("GET", "/positions")[1]["items"][0]["position_id"]
job = admin.call("GET", "/jobs")[1]["items"][0]["job_id"]
s, child = admin.call("POST", "/departments", {"department_name": f"플랫폼{tag}", "department_code": f"PLT{tag}", "parent_department_id": dev})
child_id = child["department_id"]
s, e = admin.call("POST", "/employees", {"name": "플랫폼직원", "email": f"plat.{tag}@example.test", "phone": "010-5555-0000",
    "department_id": child_id, "position_id": pos, "job_id": job, "hire_date": date.today().isoformat(),
    "employment_type": "FULL_TIME", "grant_access": True, "username": f"plat{tag}"})
check("S1 준비: 개발팀 하위 '플랫폼' 부서와 직원 계정", s == 201 and e.get("temporary_password"), f"{s} {code(e)}")
dev_emp, design_emp, plat = Client(), Client(), Client()
m3 = dev_emp.login("employee03"); dev_emp_me = m3
design_emp.login("employee04"); plat.login(f"plat{tag}", e["temporary_password"])
check("S2 사원 메뉴에도 일정과 대시보드", {"SCHEDULE", "DASHBOARD"} <= set(m3["menus"]), f"{m3['menus']}")
s, js = dev_emp.call("GET", "/dashboard")
check("S3 회사 전체 대시보드 API는 계속 관리자 전용(사원 403)", s == 403, f"{s}")
s, js = dev_emp.call("GET", "/approvals/summary")
check("S4 사원 대시보드용 결재 요약 API(진행 중 포함)", s == 200 and {"my_pending", "in_progress"} <= set(js), f"{s} {js}")


def ev(title, scope, targets=None, **extra):
    body = {"title": f"{title} {tag}", "start_at": f"{day}T10:00", "end_at": f"{day}T11:00", "location": "3층 회의실", "scope": scope, **extra}
    if targets is not None:
        body["targets"] = targets
    return admin.call("POST", "/events", body)


# 등록
s, e1 = ev("전사 공지", "COMPANY")
check("E1 전사 일정 등록", s == 201 and e1["target_label"] == "전사" and e1["targets"] == [], f"{s} {e1 and e1.get('target_label')} audience={e1 and e1.get('audience_count')}")
s, e2 = ev("개발팀 회의", "DEPARTMENTS", [{"department_id": dev, "include_children": True}])
check("E2 개발팀(하위 포함) 등록", s == 201 and e2["scope"] == "DEPARTMENTS" and e2["targets"][0]["include_children"], f"{s} {e2 and e2.get('target_label')} audience={e2 and e2.get('audience_count')}")
s, e3 = ev("개발팀만", "DEPARTMENTS", [{"department_id": dev, "include_children": False}])
check("E3 개발팀(하위 제외) 등록", s == 201, f"{s} {e3 and e3.get('target_label')}")
ids = {"dev": my_ids(dev_emp), "design": my_ids(design_emp), "plat": my_ids(plat)}
check("E4 전사 일정은 모두에게", all(e1["event_id"] in v for v in ids.values()))
check("E5 개발팀(하위 포함): 개발팀, 하위 플랫폼 O / 디자인 X", e2["event_id"] in ids["dev"] and e2["event_id"] in ids["plat"] and e2["event_id"] not in ids["design"])
check("E6 개발팀(하위 제외): 개발팀 O / 하위 플랫폼 X", e3["event_id"] in ids["dev"] and e3["event_id"] not in ids["plat"])
# 기대값: 개발팀과 모든 하위 부서의 재직자를 DB 재귀 쿼리로 직접 계산 (앱의 하위 부서 계산과 독립 대조)
dev_active = int(sql("WITH RECURSIVE t AS (SELECT department_id FROM departments WHERE department_id=%d "
                     "UNION ALL SELECT d.department_id FROM departments d JOIN t ON d.parent_department_id=t.department_id) "
                     "SELECT COUNT(*) FROM employees WHERE department_id IN (SELECT department_id FROM t) "
                     "AND employment_status IN ('ACTIVE','ON_LEAVE')" % dev))
check("E7 등록 응답의 표시 대상 인원 = 개발팀+하위 재직자", e2["audience_count"] == dev_active, f"{e2['audience_count']} vs {dev_active}")
s, js = admin.call("GET", f"/events/audience?scope=DEPARTMENTS&targets={dev}:1")
check("E8 대상 인원 미리보기 API", s == 200 and js["audience_count"] == dev_active, f"{js}")

# 검증
s, js = ev("x", "DEPARTMENTS", [])
check("V1 지정 조직인데 대상 없음 422", s == 422 and field(js) == "targets", f"{s} {code(js)} {field(js)}")
s, js = ev("x", "COMPANY", [{"department_id": dev}])
check("V2 전사인데 대상 있음 422", s == 422 and field(js) == "targets", f"{s} {field(js)}")
s, js = admin.call("POST", "/events", {"title": "x", "start_at": f"{day}T11:00", "end_at": f"{day}T10:00"})
check("V3 종료가 시작보다 이름 422 INVALID_RANGE", s == 422 and code(js) == "INVALID_RANGE", f"{s} {code(js)}")
s, js = ev("x", "DEPARTMENTS", [{"department_id": 999999}])
check("V4 없는 부서 422 REFERENCE_INVALID", s == 422 and code(js) == "REFERENCE_INVALID", f"{s} {code(js)}")
other = sql("SELECT d.department_id FROM departments d WHERE d.company_id<>(SELECT company_id FROM employees WHERE email='admin01@example.test') LIMIT 1")
if other:
    s, js = ev("x", "DEPARTMENTS", [{"department_id": int(other)}])
    check("V5 다른 회사(계열사) 부서 422 REFERENCE_INVALID", s == 422 and code(js) == "REFERENCE_INVALID", f"{s} {code(js)}")
s, js = dev_emp.call("POST", "/events", {"title": "x", "start_at": f"{day}T10:00"})
check("V6 사원은 등록 403", s == 403, f"{s}")
s, js = admin.call("POST", "/events", {"title": "x", "start_at": "내일"})
check("V7 날짜 형식 오류 422", s == 422 and field(js) == "start_at", f"{s} {field(js)}")

# 수정
s, js = admin.call("PATCH", f"/events/{e2['event_id']}", {"targets": [{"department_id": design, "include_children": True}]})
check("U1 대상 교체(개발팀 → 디자인팀)", s == 200 and [t["department_id"] for t in js["targets"]] == [design] and js["target_label"].startswith("디자인팀"), f"{s} {js and js.get('target_label')}")
check("U2 수정 즉시 반영: 개발 X, 디자인 O", e2["event_id"] not in my_ids(dev_emp) and e2["event_id"] in my_ids(design_emp))
s, js = admin.call("PATCH", f"/events/{e2['event_id']}", {"title": f"제목만 수정 {tag}"})
check("U3 제목만 수정하면 대상 유지", s == 200 and [t["department_id"] for t in js["targets"]] == [design] and js["title"].startswith("제목만"), f"{s}")
check("U4 수정 시각 갱신", js["updated_at"] >= js["created_at"])
s, js = admin.call("PATCH", f"/events/{e2['event_id']}", {"scope": "COMPANY"})
check("U5 지정 조직 → 전사로 변경, 대상 행 삭제", s == 200 and js["targets"] == [] and sql(f"SELECT COUNT(*) FROM hr_event_departments WHERE event_id={e2['event_id']}") == "0", f"{s} {js and js.get('target_label')}")
check("U6 전사로 바뀌어 개발팀도 다시 봄", e2["event_id"] in my_ids(dev_emp))
s, js = admin.call("PATCH", f"/events/{e2['event_id']}", {"scope": "DEPARTMENTS"})
check("U7 대상 없이 지정 조직으로만 바꾸면 422", s == 422 and field(js) == "targets", f"{s} {field(js)}")

# 목록, 삭제
s, js = admin.call("GET", f"/events?from={day}&to={day}&page=1&size=100")
row = next((x for x in js["items"] if x["event_id"] == e3["event_id"]), None)
check("L1 관리자 목록에 대상 정보 포함", s == 200 and row and row["targets"] and row["target_label"].startswith("개발팀"), f"{row and row.get('target_label')}")
s, _ = admin.call("DELETE", f"/events/{e3['event_id']}")
check("D1 삭제 204 + 대상 행 CASCADE 삭제", s == 204 and sql(f"SELECT COUNT(*) FROM hr_event_departments WHERE event_id={e3['event_id']}") == "0", f"{s}")
check("D2 삭제 즉시 개발팀 화면에서 사라짐", e3["event_id"] not in my_ids(dev_emp))
s, js = admin.call("DELETE", f"/events/{e3['event_id']}")
check("D3 없는 일정 삭제 404", s == 404, f"{s}")

# 사용 중지된 대상 부서
s, tmp = admin.call("POST", "/departments", {"department_name": f"임시{tag}", "department_code": f"TMP{tag}"})
s, e4 = ev("임시팀 일정", "DEPARTMENTS", [{"department_id": tmp["department_id"]}])
s, _ = admin.call("DELETE", f"/departments/{tmp['department_id']}")
s, js = admin.call("GET", f"/events?from={day}&to={day}&page=1&size=100")
row = next((x for x in js["items"] if x["event_id"] == e4["event_id"]), {})
check("X1 부서 사용 중지 후 목록에 is_active=false", row.get("targets") and row["targets"][0]["is_active"] is False, f"{row.get('targets')}")
s, js = admin.call("PATCH", f"/events/{e4['event_id']}", {"title": f"제목 {tag}"})
check("X2 대상은 두고 제목만 수정은 가능", s == 200, f"{s}")
s, js = admin.call("PATCH", f"/events/{e4['event_id']}", {"targets": [{"department_id": tmp["department_id"]}]})
check("X3 사용 중지 부서를 대상으로 저장 422", s == 422 and field(js) == "targets", f"{s} {field(js)}")

# 계열사 격리
if os.path.exists(MEDIA):
    mc = {r["username"]: r["password"] for r in csv.DictReader(open(MEDIA))}
    media = Client(); media.login("media02", mc["media02"])
    check("I1 계열사 사원 내 일정에 본사 전사 일정 없음", e1["event_id"] not in my_ids(media))
    media_id = int(sql("SELECT company_id FROM employees WHERE email='media02@example.test'"))
    admin.call("POST", "/auth/active-company", {"company_id": media_id})
    s, js = admin.call("GET", f"/events?from={day}&to={day}&page=1&size=100")
    check("I2 계열사로 전환하면 관리자 목록에 본사 일정 없음", s == 200 and all(x["event_id"] != e1["event_id"] for x in js["items"]), f"{s}")
    admin.call("POST", "/auth/active-company", {"company_id": int(sql("SELECT company_id FROM employees WHERE email='admin01@example.test'"))})
else:
    print("SKIP I1/I2 계열사 격리 (.seed-credentials-media.csv 없음)")

# 정리(테스트로 만든 일정)
for x in (e1, e2, e4):
    admin.call("DELETE", f"/events/{x['event_id']}")
passed = sum(ok for _, ok in results)
print(f"\n{passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
