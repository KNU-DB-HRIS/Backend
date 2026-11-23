#!/usr/bin/env python3
"""비밀번호 재설정 확인 (CI용): setup/reset-demo-passwords.sh 실행 전후로
예전 세션과 예전 비밀번호는 거부되고 새 비밀번호로 10개 계정 모두 로그인되는지 확인

usage: python3 tests/ci_reset_check.py <api_base> [Backend dir]
  샘플 데이터(bash ./setup/database-data.sh)가 있어야 함. 상태 코드만 출력하고 비밀번호는 출력하지 않음
"""
import csv
import http.cookiejar
import json
import os
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = sys.argv[1].rstrip("/")
ROOT = Path(sys.argv[2] if len(sys.argv) > 2 else ".").resolve()
CSV = ROOT / ".seed-credentials.csv"
results = []


class Client:
    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None):
        req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with self.op.open(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def login(self, user, password):
        return self.call("POST", "/auth/login", {"username": user, "password": password})


def check(name, ok, detail: object = ""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'} {name}  [{detail}]")


def read():
    with CSV.open(encoding="utf-8", newline="") as file:
        return {r["username"]: r["password"] for r in csv.DictReader(file)}


old = read()
before = Client()
check("재설정 전 관리자 로그인(예전 비밀번호)", before.login("admin01", old["admin01"]) == 200)
check("재설정 전 세션으로 /auth/me", before.call("GET", "/auth/me") == 200)

run = subprocess.run(["bash", "./setup/reset-demo-passwords.sh"], cwd=ROOT, capture_output=True, text=True)
new = read()
leaked = [u for u, p in new.items() if p in run.stdout or p in run.stderr]
check("재설정 스크립트 성공", run.returncode == 0, f"exit={run.returncode}")
check("출력에 비밀번호가 없음", not leaked, f"leaked={len(leaked)}")
check("새 파일: 10개 계정, 모두 바뀐 비밀번호", len(new) == 10 and set(new) == set(old) and all(new[u] != old[u] for u in new), len(new))
check("새 파일 권한 600", stat.S_IMODE(os.stat(CSV).st_mode) == 0o600, oct(stat.S_IMODE(os.stat(CSV).st_mode)))
check("임시 파일 남지 않음", not list(ROOT.glob(".seed-credentials.new.*")), "")

check("재설정 전 세션은 끊김(/auth/me 401)", before.call("GET", "/auth/me") == 401)
check("예전 비밀번호는 401", Client().login("admin01", old["admin01"]) == 401)
ok = [u for u, p in new.items() if Client().login(u, p) == 200]
check("새 비밀번호로 10개 계정 모두 로그인", len(ok) == 10, f"{len(ok)}/10")

bad = subprocess.run(["docker", "compose", "exec", "-T", "backend", "flask", "--app", "wsgi:app", "reset-passwords"],
                     cwd=ROOT, input=json.dumps({"admin01": "x" * 16, "no-such-user": "y" * 16}), capture_output=True, text=True)
check("없는 계정이 섞이면 전부 취소(admin01 비밀번호 유지)", bad.returncode != 0 and Client().login("admin01", new["admin01"]) == 200, f"exit={bad.returncode}")

print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
