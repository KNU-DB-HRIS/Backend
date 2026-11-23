#!/usr/bin/env python3
"""A 묶음 E2E: 결재자 후보(USER-01), 임시 저장 수정/삭제(APR-08/09), 발급 문서 목록(DOC-05),
단계 평가 제출과 내가 할 평가(EVAL-04/05), 급여 변경 등록(SAL-04)을 실제 API로 검증

usage: python3 tests/e2e_features_a.py <api_base> <Backend dir>
  샘플 데이터(bash ./setup/database-data.sh) 필요. 테스트가 만든 데이터는 끝에 모두 지움. 비밀번호는 출력하지 않음
"""
import csv
import http.cookiejar
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

API, BDIR = sys.argv[1].rstrip("/"), sys.argv[2]
with open(f"{BDIR}/.seed-credentials.csv", encoding="utf-8", newline="") as file:
    CREDS = {r["username"]: r["password"] for r in csv.DictReader(file)}
results = []
made = {"approvals": [], "documents": [], "salary": [], "evaluations": [], "periods": [], "salary_restore": None}


class Client:
    def __init__(self, user=None):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = None
        if user:
            s, _ = self.call("POST", "/auth/login", {"username": user, "password": CREDS[user]})
            assert s == 200, f"login {user} -> {s}"
            self.me = self.call("GET", "/auth/me")[1]

    def call(self, method, path, body=None, raw=False):
        req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, method=method)
        req.add_header("Content-Type", "application/json")
        if self.csrf and method != "GET":
            req.add_header("X-CSRF-Token", self.csrf)
        try:
            with self.op.open(req, timeout=40) as r:
                data, status = r.read(), r.status
        except urllib.error.HTTPError as e:
            data, status = e.read(), e.code
        if raw:
            return status, data
        try:
            js = json.loads(data) if data else None
        except ValueError:
            js = None
        if isinstance(js, dict) and js.get("csrf_token"):
            self.csrf = js["csrf_token"]
        return status, js


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail != "" else ""))


def code(js):
    return js.get("error", {}).get("code") if isinstance(js, dict) else None


def field(js):
    return (js.get("error", {}).get("details") or {}).get("field") if isinstance(js, dict) else None


def sql(q):
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", "mysql", "sh", "-c",
         f'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -N -e "SET time_zone=\'+09:00\'; {q}"'],
        cwd=BDIR, capture_output=True, text=True,
    )
    return out.stdout.strip()


def ids_in(values):
    return ",".join(str(int(v)) for v in values) or "0"


# ---------------- 준비 ----------------
TODAY = date.fromisoformat(sql("SELECT CURDATE()"))
people = {}
for line in sql("SELECT u.username,u.user_id,u.employee_id,e.department_id,e.company_id,e.employment_status "
                "FROM users u JOIN employees e ON e.employee_id=u.employee_id").splitlines():
    name, uid, eid, dep, comp, status = line.split("\t")
    people[name] = {"user_id": int(uid), "employee_id": int(eid), "department_id": int(dep), "company_id": int(comp), "status": status}
for name in ("admin01", "employee02", "employee03", "employee04", "employee07", "employee08", "employee10"):
    assert name in people and name in CREDS, f"sample account {name} missing"


def run():
    admin, emp03, emp08, emp04, emp02 = (Client(u) for u in ("admin01", "employee03", "employee08", "employee04", "employee02"))
    anon = Client()

    # ---------------- USER-01 결재자 후보 ----------------
    s, js = emp03.call("GET", "/users/approvers")
    ids = [x["user_id"] for x in (js or {}).get("items", [])]
    check("U1 결재자 후보 조회", s == 200 and ids and js["total"] >= len(ids), f"{s} items={len(ids)} total={(js or {}).get('total')}")
    check("U2 본인 제외", people["employee03"]["user_id"] not in ids)
    check("U3 휴직자 제외", people["employee10"]["user_id"] not in ids, "employee10=ON_LEAVE")
    check("U4 필드: 이름, 부서, 직급, 직책(연락처 없음)", js and set(js["items"][0]) == {"user_id", "name", "department_name", "position_name", "job_title_name"}, sorted(js["items"][0]) if js and js["items"] else "")
    s, js2 = emp03.call("GET", "/users/approvers?q=" + urllib.parse.quote("개발"))
    check("U5 q=개발: 이름 또는 부서 일치만", s == 200 and js2["items"] and all("개발" in x["name"] or "개발" in x["department_name"] for x in js2["items"]), f"{s} {len(js2['items']) if js2 else '-'}")
    s, js3 = emp03.call("GET", "/users/approvers?q=" + urllib.parse.quote("없는이름xyz"))
    check("U6 결과 없음은 200, 빈 목록", s == 200 and js3["items"] == [] and js3["total"] == 0, s)
    s0, _ = emp03.call("GET", "/users/approvers?limit=0")
    s51, _ = emp03.call("GET", "/users/approvers?limit=51")
    check("U7 limit=0, 51은 422", s0 == 422 and s51 == 422, f"{s0} {s51}")
    s, _ = anon.call("GET", "/users/approvers")
    check("U8 로그인 없으면 401", s == 401, s)
    s, js = emp03.call("POST", "/approvals", {"request_type": "GENERAL", "title": "E2E 휴직자 결재선", "approver_user_ids": [people["employee10"]["user_id"]], "submit": False})
    check("U9 휴직자를 결재선에 넣으면 422 APPROVERS_INVALID", s == 422 and code(js) == "APPROVERS_INVALID", f"{s} {code(js)}")
    if s == 201:
        made["approvals"].append(js["request_id"])

    # ---------------- APR-08/09 임시 저장 수정/삭제 ----------------
    a, b = people["employee02"]["user_id"], people["admin01"]["user_id"]
    s, d = emp03.call("POST", "/approvals", {"request_type": "LEAVE", "title": "E2E 초안", "content": "결재선 없음", "submit": False})
    rid = d and d.get("request_id")
    if rid:
        made["approvals"].append(rid)
    check("A1 결재선 없는 초안: 수정/삭제만, 상신 불가", s == 201 and d["allowed_actions"] == ["EDIT", "DELETE"], f"{s} {d and d.get('allowed_actions')}")
    s, d = emp03.call("PATCH", f"/approvals/{rid}", {"title": "E2E 초안(수정)", "approver_user_ids": [a, b]})
    check("A2 제목과 결재선 수정 → 상신 가능", s == 200 and d["title"] == "E2E 초안(수정)" and [x["approver_user_id"] for x in d["steps"]] == [a, b]
          and all(x["status"] == "WAITING" for x in d["steps"]) and "SUBMIT" in d["allowed_actions"], f"{s} {d and d.get('allowed_actions')}")
    s, d = emp03.call("PATCH", f"/approvals/{rid}", {"content": "본문만 수정"})
    check("A3 결재선을 안 보내면 유지", s == 200 and len(d["steps"]) == 2 and d["content"] == "본문만 수정", s)
    s1, j1 = emp03.call("PATCH", f"/approvals/{rid}", {})
    s2, j2 = emp03.call("PATCH", f"/approvals/{rid}", {"status": "APPROVED"})
    check("A4 빈 본문, 모르는 필드(status)는 422", s1 == 422 and s2 == 422, f"{s1} {code(j1)} / {s2} {code(j2)}")
    s1, j1 = emp03.call("PATCH", f"/approvals/{rid}", {"approver_user_ids": [people["employee03"]["user_id"]]})
    six = [p["user_id"] for n, p in people.items() if n not in ("employee03", "employee10")][:6]
    s2, j2 = emp03.call("PATCH", f"/approvals/{rid}", {"approver_user_ids": six})
    check("A5 본인 포함, 6명 결재선은 422", code(j1) == "APPROVERS_INVALID" and code(j2) == "APPROVERS_INVALID", f"{s1} {s2} n={len(six)}")
    s1, j1 = emp08.call("PATCH", f"/approvals/{rid}", {"title": "남의 초안"})
    s2, j2 = emp08.call("DELETE", f"/approvals/{rid}")
    check("A6 남의 초안 수정/삭제는 403 NOT_REQUESTER", s1 == 403 and s2 == 403 and code(j1) == code(j2) == "NOT_REQUESTER", f"{s1} {s2}")
    s, d = emp03.call("POST", f"/approvals/{rid}/submit")
    check("A7 수정한 초안 상신", s == 200 and d["status"] == "IN_PROGRESS", s)
    s1, j1 = emp03.call("PATCH", f"/approvals/{rid}", {"title": "상신 뒤 수정"})
    s2, j2 = emp03.call("DELETE", f"/approvals/{rid}")
    check("A8 상신된 문서 수정/삭제는 409 INVALID_STATE", s1 == 409 and s2 == 409 and code(j1) == code(j2) == "INVALID_STATE", f"{s1} {s2}")
    s, d = emp03.call("POST", "/approvals", {"request_type": "GENERAL", "title": "E2E 버릴 초안", "approver_user_ids": [a], "submit": False})
    rid2 = d and d.get("request_id")
    if rid2:
        made["approvals"].append(rid2)
    s1, _ = emp03.call("DELETE", f"/approvals/{rid2}")
    s2, _ = emp03.call("GET", f"/approvals/{rid2}")
    s3, _ = emp03.call("DELETE", f"/approvals/{rid2}")
    left = sql(f"SELECT COUNT(*) FROM approval_steps WHERE approval_request_id={int(rid2)}")
    check("A9 초안 삭제 204 → 조회 404, 단계도 삭제", s1 == 204 and s2 == 404 and s3 == 404 and left == "0", f"{s1} {s2} {s3} steps={left}")

    # ---------------- DOC-05 발급 문서 목록 ----------------
    me3 = people["employee03"]["employee_id"]
    s, doc = emp03.call("POST", "/certificates", {"employee_id": me3, "certificate_type": "EMPLOYMENT"})
    doc_id = doc and doc.get("document_id")
    if doc_id:
        made["documents"].append(doc_id)
    s, js = emp03.call("GET", "/documents?page=1&size=100")
    items = (js or {}).get("items", [])
    check("D1 사원: 본인 문서만, 방금 발급한 문서 포함", s == 200 and any(x["document_id"] == doc_id for x in items) and all(x["employee_id"] == me3 for x in items), f"{s} n={len(items)}")
    row = next((x for x in items if x["document_id"] == doc_id), {})
    check("D2 항목: 종류, 파일명, 발급자, 내려받기 주소", row.get("document_type") == "EMPLOYMENT" and row.get("issued_by_name") == "박하린"
          and row.get("file_url") == f"/api/v1/documents/{doc_id}/file", f"{row.get('issued_by_name')} {row.get('file_url')}")
    s, js = emp03.call("GET", f"/documents?employee_id={people['employee04']['employee_id']}")
    check("D3 사원이 남의 employee_id → 403 FORBIDDEN_SCOPE", s == 403 and code(js) == "FORBIDDEN_SCOPE", s)
    s, js = emp03.call("GET", "/documents?document_type=PAYSLIP")
    check("D4 종류 필터", s == 200 and all(x["document_type"] == "PAYSLIP" for x in js["items"]), f"{s} n={len(js['items']) if js else '-'}")
    s, js = emp03.call("GET", "/documents?document_type=RESUME")
    check("D5 없는 종류는 422", s == 422, s)
    s, js = admin.call("GET", f"/documents?employee_id={me3}&size=5")
    check("D6 관리자: 직원 필터로 그 직원 문서", s == 200 and any(x["document_id"] == doc_id for x in js["items"]) and all(x["employee_id"] == me3 for x in js["items"]), s)
    s, pdf = emp03.call("GET", f"/documents/{doc_id}/file", raw=True)
    check("D7 목록의 주소로 PDF 내려받기", s == 200 and pdf[:4] == b"%PDF", f"{s} bytes={len(pdf)}")

    # ---------------- EVAL-04/05 단계 평가 ----------------
    company = people["employee03"]["company_id"]
    leader = people["admin01"]["employee_id"]
    sql("SET @y:=2099; DELETE r FROM evaluation_stage_records r JOIN employee_evaluations v ON v.employee_evaluation_id=r.evaluation_id "
        "JOIN evaluation_periods p ON p.evaluation_period_id=v.evaluation_period_id WHERE p.evaluation_year=@y; "
        "DELETE v FROM employee_evaluations v JOIN evaluation_periods p ON p.evaluation_period_id=v.evaluation_period_id WHERE p.evaluation_year=@y; "
        "DELETE FROM evaluation_periods WHERE evaluation_year=@y")
    p_open = int(sql(f"INSERT INTO evaluation_periods(company_id,evaluation_year,evaluation_half,start_date,end_date,status) "
                     f"VALUES({company},2099,'H1','{TODAY - timedelta(days=1)}','{TODAY + timedelta(days=1)}','IN_PROGRESS'); SELECT LAST_INSERT_ID()"))
    p_closed = int(sql(f"INSERT INTO evaluation_periods(company_id,evaluation_year,evaluation_half,start_date,end_date,status) "
                       f"VALUES({company},2099,'H2','{TODAY - timedelta(days=30)}','{TODAY - timedelta(days=1)}','IN_PROGRESS'); SELECT LAST_INSERT_ID()"))
    made["periods"] += [p_open, p_closed]
    e1 = int(sql(f"INSERT INTO employee_evaluations(employee_id,evaluator_employee_id,evaluation_period_id,status) "
                 f"VALUES({me3},{leader},{p_open},'IN_PROGRESS'); SELECT LAST_INSERT_ID()"))
    e2 = int(sql(f"INSERT INTO employee_evaluations(employee_id,evaluator_employee_id,evaluation_period_id,status) "
                 f"VALUES({me3},{leader},{p_closed},'IN_PROGRESS'); SELECT LAST_INSERT_ID()"))
    made["evaluations"] += [e1, e2]

    def tasks(client):
        s, js = client.call("GET", "/me/evaluation-tasks")
        return s, {(t["evaluation_id"], t["stage"]) for t in (js or {}).get("items", [])}, js

    def submit(client, evaluation, stage, score=None, comment=None):
        body = {"stage": stage}
        if score is not None:
            body["score"] = score
        if comment is not None:
            body["comment"] = comment
        return client.call("POST", f"/evaluations/{evaluation}/stage-records", body)

    check("V0 사원 메뉴에 평가, 회차 현황 API는 계속 관리자 전용",
          "EVALUATION" in emp03.me["menus"] and emp03.call("GET", "/evaluation-periods")[0] == 403, emp03.me["menus"])
    s, t3, _ = tasks(emp03)
    check("V1 대상자에게 목표 설정 할 일", s == 200 and (e1, "GOAL") in t3 and not any(e == e2 for e, _ in t3), f"{s} {sorted(st for e, st in t3 if e == e1)}")
    s, js = submit(emp03, e1, "SELF", 80)
    check("V2 목표 전에 자기 평가는 409 STAGE_ORDER", s == 409 and code(js) == "STAGE_ORDER", f"{s} {code(js)}")
    s1, j1 = submit(emp03, e1, "GOAL", 50, "목표")
    s2, j2 = submit(emp03, e1, "GOAL")
    check("V3 목표에 점수는 422, 목표 내용 없으면 422", s1 == 422 and field(j1) == "score" and s2 == 422 and field(j2) == "comment", f"{field(j1)} {field(j2)}")
    s, js = submit(emp03, e1, "GOAL", comment="리포트 자동화로 월 20시간 절감")
    check("V4 목표 설정 제출 → 자기 평가 단계, 25%", s == 201 and js["current_stage"] == "SELF" and js["progress_rate"] == 0.25 and js["evaluator_employee_id"] == me3, f"{s} {js and js.get('current_stage')}")
    s, js = submit(emp03, e1, "GOAL", comment="다시")
    check("V5 같은 단계 재제출은 409", s == 409 and code(js) == "STAGE_ALREADY_SUBMITTED", s)
    s, js = submit(emp08, e1, "PEER", 70)
    check("V6 자기 평가 전에 동료 평가는 409 STAGE_ORDER", s == 409 and code(js) == "STAGE_ORDER", f"{s} {code(js)}")
    s1, j1 = submit(emp03, e1, "SELF", 101)
    s2, j2 = submit(emp03, e1, "SELF", 80, "자기 평가")
    check("V7 점수 101은 422, 자기 평가 제출 → 50%", s1 == 422 and s2 == 201 and j2["progress_rate"] == 0.5 and j2["current_stage"] == "PEER", f"{s1} {s2}")
    s, t8, _ = tasks(emp08)
    check("V8 같은 부서 동료에게 동료 평가 할 일", (e1, "PEER") in t8, s)
    s1, j1 = submit(admin, e1, "PEER", 70)
    s2, j2 = submit(emp04, e1, "PEER", 70)
    s3, j3 = submit(emp08, e1, "LEADER", 70)
    check("V9 리더의 동료 평가, 다른 부서, 리더 아닌 사람의 리더 평가는 403", s1 == s2 == s3 == 403 and code(j1) == code(j2) == code(j3) == "NOT_STAGE_EVALUATOR", f"{s1} {s2} {s3}")
    s, js = submit(admin, e1, "LEADER", 90)
    check("V10 동료 평가 전에 리더 평가는 409 STAGE_ORDER", s == 409 and code(js) == "STAGE_ORDER", s)
    s, js = submit(emp08, e1, "PEER", 75, "협업 좋음")
    check("V11 동료 평가 → 75%, 리더 평가 단계", s == 201 and js["progress_rate"] == 0.75 and js["current_stage"] == "LEADER", s)
    s, js = submit(emp08, e1, "PEER", 75)
    check("V12 같은 동료 재제출은 409", s == 409 and code(js) == "STAGE_ALREADY_SUBMITTED", s)
    s, ta, _ = tasks(admin)
    check("V13 리더에게 리더 평가 할 일", (e1, "LEADER") in ta, s)
    s, js = submit(admin, e1, "LEADER", 90, "목표 달성")
    status = sql(f"SELECT status FROM employee_evaluations WHERE employee_evaluation_id={e1}")
    check("V14 리더 평가 → 완료 100%, 평가 상태 COMPLETED", s == 201 and js["current_stage"] == "COMPLETED" and js["progress_rate"] == 1 and status == "COMPLETED", f"{s} {status}")
    s, js = submit(emp02, e1, "PEER", 80)
    check("V15 리더 평가 뒤 동료 평가는 409 STAGE_ORDER", s == 409 and code(js) == "STAGE_ORDER", f"{s} {code(js)}")
    s, js = submit(emp03, e2, "GOAL", comment="기간 끝난 회차")
    check("V16 기간이 끝난 회차는 409 PERIOD_CLOSED", s == 409 and code(js) == "PERIOD_CLOSED", s)
    s, js = submit(emp03, 999999999, "GOAL", comment="x")
    check("V17 없는 평가는 404", s == 404 and code(js) == "EVALUATION_NOT_FOUND", s)
    s, t3, js = tasks(emp03)
    mine = {(x["evaluation_id"], x["stage"]) for x in js["submitted"]}
    check("V18 완료 뒤 할 일에서 빠지고, 낸 평가에 목표/자기 평가", not any(e == e1 for e, _ in t3) and {(e1, "GOAL"), (e1, "SELF")} <= mine, f"{sorted(mine)}")

    # ---------------- SAL-04 급여 변경 등록 (적용일은 오늘 이전만, sp_change_salary와 같은 규칙) ----------------
    target = None
    for name in ("employee07", "employee08", "employee09"):
        eid = people[name]["employee_id"]
        if sql(f"SELECT COUNT(*) FROM salary_history WHERE employee_id={eid} AND effective_date>=CURDATE()") == "0":
            target = eid
            break
    check("S0 준비: 오늘 이후 급여 이력이 없는 사원", target is not None, target)
    last_date, last_total, current_cache, hire = sql(
        f"SELECT h.effective_date,h.new_salary,IFNULL(e.current_salary,'NULL'),e.hire_date FROM salary_history h JOIN employees e ON e.employee_id=h.employee_id "
        f"WHERE h.employee_id={target} ORDER BY h.effective_date DESC,h.salary_history_id DESC LIMIT 1").split("\t")
    made["salary_restore"] = (target, current_cache)
    last_date, hire = date.fromisoformat(last_date), date.fromisoformat(hire)
    last_parts = [int(float(x)) for x in sql(
        f"SELECT base_salary,position_allowance,meal_allowance,other_allowance FROM salary_history WHERE employee_id={target} "
        "ORDER BY effective_date DESC,salary_history_id DESC LIMIT 1").split("\t")]

    def change(client, day, base=3000000, pos=200000, meal=200000, other=100000, reason="E2E 급여 변경", **extra):
        body = {"effective_date": str(day), "base_salary": base, "position_allowance": pos, "meal_allowance": meal, "other_allowance": other, "reason": reason, **extra}
        s, js = client.call("POST", f"/employees/{target}/salary-history", body)
        if s == 201:
            made["salary"].append(js["salary_history_id"])
        return s, js

    def view():
        return int(float(sql(f"SELECT current_salary FROM vw_current_salaries WHERE employee_id={target}")))

    s, js = change(emp03, TODAY)
    check("S1 사원은 403", s == 403, s)
    s, js = change(admin, hire - timedelta(days=1))
    check("S2 입사일 전은 422 EFFECTIVE_BEFORE_HIRE", s == 422 and code(js) == "EFFECTIVE_BEFORE_HIRE", f"{s} {code(js)}")
    s1, j1 = change(admin, TODAY + timedelta(days=1))
    s2, j2 = change(admin, TODAY + timedelta(days=30))
    check("S3 미래 적용일(내일, 30일 뒤)은 422 FUTURE_DATE_NOT_SUPPORTED", s1 == s2 == 422 and code(j1) == code(j2) == "FUTURE_DATE_NOT_SUPPORTED", f"{s1} {s2} {code(j1)}")
    s, js = change(admin, last_date)
    check("S4 같은 적용일은 409 EFFECTIVE_DATE_TAKEN", s == 409 and code(js) == "EFFECTIVE_DATE_TAKEN", f"{s} {code(js)}")
    if last_date - timedelta(days=1) >= hire:
        s, js = change(admin, last_date - timedelta(days=1))
        check("S5 최신보다 앞선 적용일은 409 EFFECTIVE_DATE_NOT_LATEST", s == 409 and code(js) == "EFFECTIVE_DATE_NOT_LATEST", f"{s} {code(js)}")
    s1, _ = change(admin, TODAY, base=-1)
    s2, _ = change(admin, TODAY, base=True)
    s3, _ = admin.call("POST", f"/employees/{target}/salary-history", {"effective_date": str(TODAY), "base_salary": 1, "position_allowance": 0, "meal_allowance": 0, "other_allowance": 0})
    s4, _ = change(admin, TODAY, new_salary=999)
    check("S6 음수, true, 사유 누락, 총액 직접 입력은 422", (s1, s2, s3, s4) == (422, 422, 422, 422), f"{s1} {s2} {s3} {s4}")
    s, js = change(admin, TODAY, *last_parts, reason="같은 금액")
    check("S7 네 항목이 직전과 같으면 422 NO_CHANGE", s == 422 and code(js) == "NO_CHANGE", f"{s} {code(js)}")
    s, js = change(admin, TODAY)
    check("S8 오늘 적용: 총액은 네 항목 합, 이전 급여 = 직전 행, is_current", s == 201 and js["new_salary"] == 3500000 and js["previous_salary"] == int(float(last_total))
          and js["change_amount"] == 3500000 - int(float(last_total)) and js["components_status"] == "COMPLETE" and js["is_current"], f"{s} {js and js.get('new_salary')}")
    s, cur = admin.call("GET", f"/employees/{target}/salary")
    s2, lst = admin.call("GET", "/salaries?size=100")
    listed = next((x["current_salary"] for x in (lst or {}).get("items", []) if x["employee_id"] == target), None)
    check("S9 현재 급여 API, 목록, 보고 뷰(vw_current_salaries)가 모두 같은 값", cur["total"] == listed == view() == 3500000,
          f"api={cur and cur.get('total')} list={listed} view={view()}")
    s, js = change(admin, TODAY, base=3100000)
    check("S10 같은 날 두 번째 변경은 409 EFFECTIVE_DATE_TAKEN", s == 409 and code(js) == "EFFECTIVE_DATE_TAKEN", f"{s} {code(js)}")
    s, h = admin.call("GET", f"/employees/{target}/salary-history")
    check("S11 이력에 오늘 변경이 마지막 행", s == 200 and h["items"][-1]["effective_date"] == str(TODAY) and h["items"][-1]["new_salary"] == 3500000, s)

    # ---------------- 통합 검색: 사원도 구성원(사내 주소록 수준) ----------------
    name04 = sql(f"SELECT employee_name FROM employees WHERE employee_id={people['employee04']['employee_id']}")
    s, js = emp03.call("GET", "/search?q=" + urllib.parse.quote(name04))
    items = (js or {}).get("employees", {}).get("items", [])
    hit = next((x for x in items if x["employee_id"] == people["employee04"]["employee_id"]), None)
    check("Q1 사원 검색: 이름으로 다른 부서 구성원 찾음", s == 200 and hit is not None, f"{s} n={len(items)}")
    check("Q2 사원 검색 필드: 사번, 이름, 부서, 직급만(연락처·재직 상태 없음)", hit and set(hit) == {"employee_id", "employee_no", "name", "department_name", "position_name"}, sorted(hit) if hit else "")
    s, js = emp03.call("GET", "/search?q=" + urllib.parse.quote("개발"))
    items = (js or {}).get("employees", {}).get("items", [])
    check("Q3 사원 검색: 부서 이름으로 찾음", s == 200 and items and all("개발" in x["name"] or "개발" in x["department_name"] for x in items), f"{s} n={len(items)}")
    left = sql("SELECT COUNT(*) FROM employees WHERE employment_status='TERMINATED' AND employee_id IN (" + (",".join(str(x["employee_id"]) for x in items) or "0") + ")")
    check("Q4 사원 검색에 퇴사자 없음", left == "0", left)
    s, js = admin.call("GET", "/search?q=" + urllib.parse.quote(name04))
    a_items = (js or {}).get("employees", {}).get("items", [])
    check("Q5 관리자 검색은 그대로(재직 상태 포함)", s == 200 and a_items and "employment_status" in a_items[0], f"{s}")


def cleanup():
    if made["approvals"]:
        ids = ids_in(made["approvals"])
        sql(f"DELETE FROM approval_steps WHERE approval_request_id IN ({ids}); DELETE FROM approval_requests WHERE approval_request_id IN ({ids})")
    if made["documents"]:
        paths = sql(f"SELECT file_path FROM documents WHERE document_id IN ({ids_in(made['documents'])})").split()
        for path in paths:
            subprocess.run(["docker", "compose", "exec", "-T", "backend", "sh", "-c", f'rm -f "$STORAGE_DIR/{path}"'], cwd=BDIR, capture_output=True)
        sql(f"DELETE FROM documents WHERE document_id IN ({ids_in(made['documents'])})")
    if made["salary"]:
        sql(f"DELETE FROM salary_history WHERE salary_history_id IN ({ids_in(made['salary'])})")
    if made["salary_restore"]:
        target, value = made["salary_restore"]
        sql(f"UPDATE employees SET current_salary={value} WHERE employee_id={int(target)}")
    if made["evaluations"]:
        ids = ids_in(made["evaluations"])
        sql(f"DELETE FROM evaluation_stage_records WHERE evaluation_id IN ({ids}); DELETE FROM employee_evaluations WHERE employee_evaluation_id IN ({ids})")
    if made["periods"]:
        sql(f"DELETE FROM evaluation_periods WHERE evaluation_period_id IN ({ids_in(made['periods'])})")
    leftovers = sql("SELECT (SELECT COUNT(*) FROM approval_requests WHERE title LIKE 'E2E %') + "
                    "(SELECT COUNT(*) FROM evaluation_periods WHERE evaluation_year=2099) + "
                    "(SELECT COUNT(*) FROM salary_history WHERE reason LIKE 'E2E %')")
    check("Z 테스트 데이터 정리 (남은 행 0)", leftovers == "0", leftovers)


try:
    run()
finally:
    cleanup()
passed = sum(ok for _, ok in results)
print(f"{passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
