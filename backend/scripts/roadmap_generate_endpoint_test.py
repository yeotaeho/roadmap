# generate 엔드포인트 계약 테스트 — 라우트 등록·인증 가드(무LLM)
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_pass = 0
_fail = 0


def check(name: str, cond: bool) -> None:
    global _pass, _fail
    if cond:
        _pass += 1
        print(f"PASS {name}")
    else:
        _fail += 1
        print(f"FAIL {name}")


def main() -> int:
    from main import app

    paths = {getattr(r, "path", None): r for r in app.routes}
    check("POST /generate 등록", "/api/roadmap/generate" in paths)
    check("GET /generate/status 등록", "/api/roadmap/generate/status" in paths)
    check("GET /generate/stream 등록", "/api/roadmap/generate/stream" in paths)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    check("무인증 generate 401", client.post("/api/roadmap/generate").status_code == 401)
    check("무인증 status 401", client.get("/api/roadmap/generate/status").status_code == 401)
    check("무인증 stream 401", client.get("/api/roadmap/generate/stream").status_code == 401)

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
