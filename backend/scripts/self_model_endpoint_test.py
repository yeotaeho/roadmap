# 자기모델 엔드포인트 — GET 라운드트립·camelCase·민감 제외·무토큰 401

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

import httpx
from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.auth.hub.security.services.jwt import JWTService
from domain.user_intelligence.hub.repositories.self_model_repository import SelfModelRepository

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


async def _uid(s) -> str:
    r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
    if r is None:
        raise SystemExit("users 테이블이 비어 있습니다.")
    return str(r.id)


async def _cleanup(s, uid: str) -> None:
    await s.execute(text("DELETE FROM user_self_model_evidence WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    from main import app

    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)
        repo = SelfModelRepository(s)
        await repo.write_self_model(uid, {"top_codes": ["I"]}, None, "탐구형", {"riasec": 0.7}, "coach_extraction")
        await repo.append_evidence(
            uid,
            [
                {"dimension": "like", "content": "발표를 좋아함"},
                {"dimension": "constraint", "content": "통근 제약", "is_sensitive": True},
            ],
            "coach_extraction",
        )

    token = JWTService().generate_token(uid, provider="test", email="sm@test.local")
    headers = {"Authorization": f"Bearer {token}"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/user/self-model", headers=headers)
        check("GET 200", r.status_code == 200, str(r.status_code))
        sm = r.json().get("selfModel", {})
        check("riasec 반영", sm.get("riasec") == {"top_codes": ["I"]}, str(sm.get("riasec")))
        check("narrativeSummary camelCase", sm.get("narrativeSummary") == "탐구형")
        ev = sm.get("evidence", [])
        check("비민감 근거 포함", any(e["dimension"] == "like" for e in ev))
        check("민감 근거 제외", all(e["dimension"] != "constraint" for e in ev), str(ev))
        r2 = await c.get("/api/user/self-model")
        check("무토큰 401", r2.status_code == 401, str(r2.status_code))

    async with AsyncSessionLocal() as s:
        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
