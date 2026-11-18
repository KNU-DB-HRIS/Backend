#!/usr/bin/env python3
"""새로 설치한 서버의 기본 동작 확인 (CI용): 상태 확인, 로그인, 역할별 권한

usage: python3 tests/ci_smoke.py <api_base> [Backend dir]
  예: python3 tests/ci_smoke.py http://127.0.0.1:8080/api/v1 .
  샘플 데이터(bash ./setup/database-data.sh)가 있어야 함. 공개 로그용이라 상태 코드만 출력하고 비밀번호는 출력하지 않음
"""
import csv
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = sys.argv[1].rstrip("/")
ROOT = Path(sys.argv[2] if len(sys.argv) > 2 else ".")
HEALTH = API.rsplit("/api/", 1)[0] + "/health/ready"
results = []


class Client:
    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, url, body=None):
        url = url if url.startswith("http") else API + url
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with self.op.open(req, timeout=30) as r:
                raw, status = r.read(), r.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        except OSError as e:
            return 0, {"error": type(e).__name__}
        try:
            return status, json.loads(raw) if raw else None
        except ValueError:
            return status, None


def check(name, ok, detail: object = ""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'} {name}  [{detail}]")


rows = list(csv.DictReader((ROOT / ".seed-credentials.csv").open(encoding="utf-8", newline="")))
role = lambda r: (r.get("role") or "").strip()
admin = next((r for r in rows if role(r) == "HR_ADMIN"), None)
employee = next((r for r in rows if role(r) == "EMPLOYEE"), None)
check("샘플 계정(관리자, 사원) 생성됨", admin and employee, f"{len(rows)} accounts")
if not (admin and employee):
    sys.exit(1)

anon = Client()
s, _ = anon.call("GET", HEALTH)
check("상태 확인 /health/ready", s == 200, s)
s, _ = anon.call("GET", "/auth/me")
check("로그인 없이 /auth/me는 401", s == 401, s)
s, _ = anon.call("POST", "/auth/login", {"username": admin["username"], "password": "wrong-password"})
check("틀린 비밀번호는 401", s == 401, s)

a = Client()
s, _ = a.call("POST", "/auth/login", {"username": admin["username"], "password": admin["password"]})
check("관리자 로그인", s == 200, s)
s, me = a.call("GET", "/auth/me")
check("관리자 /auth/me 역할과 메뉴", s == 200 and "HR_ADMIN" in (me or {}).get("roles", []) and "DASHBOARD" in (me or {}).get("menus", []), s)
s, js = a.call("GET", "/employees?page=1&size=5")
total = int((js or {}).get("total") or 0) if isinstance(js, dict) else 0
check("관리자 직원 목록", s == 200 and total > 0, f"{s} total={total}")
for path in ("/dashboard", "/departments", "/approvals/summary"):
    s, _ = a.call("GET", path)
    check(f"관리자 {path}", s == 200, s)

e = Client()
s, _ = e.call("POST", "/auth/login", {"username": employee["username"], "password": employee["password"]})
check("사원 로그인", s == 200, s)
s, me = e.call("GET", "/auth/me")
check("사원 /auth/me 역할", s == 200 and "EMPLOYEE" in (me or {}).get("roles", []) and "HR_ADMIN" not in (me or {}).get("roles", []), s)
s, _ = e.call("GET", "/employees?page=1&size=5")
check("사원은 직원 목록 403", s == 403, s)
s, _ = e.call("GET", "/approvals/summary")
check("사원 내 결재 요약", s == 200, s)

print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
