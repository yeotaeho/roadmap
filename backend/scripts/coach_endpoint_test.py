# 코치 라우터 등록·경로 계약 단위 테스트(무DB — 앱 라우트 테이블만 검사)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from main import app

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


def run() -> int:
    routes = {(r.path, m) for r in app.routes if hasattr(r, "methods") for m in (r.methods or [])}
    check("세션 생성", ("/api/coach/sessions", "POST") in routes)
    check("스트림", ("/api/coach/stream", "POST") in routes)
    check("세션 종료", ("/api/coach/sessions/{session_id}/end", "POST") in routes)
    check("히스토리", ("/api/coach/sessions/{session_id}/messages", "GET") in routes)

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
