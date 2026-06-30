# 성향·선호 엔드포인트 인프로세스 통합 테스트 — GET/PUT 라운드트립

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402
from domain.auth.hub.security.services.jwt import JWTService  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {extra}")


async def _resolve_user() -> str:
    async with AsyncSessionLocal() as s:
        r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
        if r is None:
            raise SystemExit("users 테이블이 비어 있습니다.")
        return str(r.id)


async def run() -> int:
    from main import app

    uid = await _resolve_user()
    token = JWTService().generate_token(uid, provider="test", email="seed@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "workStyle": "challenge",
        "companySizePref": "startup",
        "workTypePref": "hybrid",
        "workValues": ["growth", "autonomy"],
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/preferences", headers=headers)
        check("GET 200", r.status_code == 200, str(r.status_code))
        check("GET success", r.json().get("success") is True)

        r = await client.put("/api/preferences", headers=headers, json=payload)
        check("PUT 200", r.status_code == 200, str(r.status_code))
        saved = r.json().get("preferences", {})
        check("PUT source=user_form", saved.get("source") == "user_form", str(saved.get("source")))

        r = await client.get("/api/preferences", headers=headers)
        p = r.json().get("preferences", {})
        check("workStyle 반영", p.get("workStyle") == "challenge")
        check("workValues 2개", len(p.get("workValues") or []) == 2, str(p.get("workValues")))
        check("companySizePref 반영", p.get("companySizePref") == "startup")

        r = await client.get("/api/preferences")
        check("무토큰 401", r.status_code == 401, str(r.status_code))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
