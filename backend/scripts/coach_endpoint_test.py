# 코치 세션 엔드포인트 — 생성·스트림(무키 경로)·messages·end·소유권 403/404·무토큰 401

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
        raise SystemExit("users 비어있음")
    return str(r.id)


async def _cleanup(s, uid: str) -> None:
    await s.execute(text(
        "DELETE FROM coach_messages WHERE session_id IN "
        "(SELECT id FROM coach_sessions WHERE user_id = CAST(:u AS UUID))"), {"u": uid})
    await s.execute(text("DELETE FROM coach_sessions WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    from main import app

    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)

    token = JWTService().generate_token(uid, provider="test", email="coach@test.local")
    h = {"Authorization": f"Bearer {token}"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/coach/sessions", headers=h)
        check("세션 생성 200", r.status_code == 200, str(r.status_code))
        sid = r.json().get("sessionId")
        check("sessionId 반환", bool(sid))

        # 스트림(무키 경로면 비활성 메시지 — 사용자 메시지는 저장됨)
        r = await c.post("/api/coach/stream", headers=h, json={"sessionId": sid, "message": "안녕"})
        check("스트림 200", r.status_code == 200, str(r.status_code))

        r = await c.get(f"/api/coach/sessions/{sid}/messages", headers=h)
        check("messages 200", r.status_code == 200)
        roles = [m["role"] for m in r.json().get("messages", [])]
        check("user 메시지 저장", "user" in roles, str(roles))

        # 소유권 — 타인 토큰
        other = JWTService().generate_token("00000000-0000-0000-0000-000000000000", provider="test", email="x@test.local")
        r = await c.get(f"/api/coach/sessions/{sid}/messages", headers={"Authorization": f"Bearer {other}"})
        check("타인 403", r.status_code == 403, str(r.status_code))

        # 미존재 404
        r = await c.get("/api/coach/sessions/11111111-1111-1111-1111-111111111111/messages", headers=h)
        check("미존재 404", r.status_code == 404, str(r.status_code))

        # 종료
        r = await c.post(f"/api/coach/sessions/{sid}/end", headers=h)
        check("end 200", r.status_code == 200)

        # 무토큰 401
        r = await c.post("/api/coach/sessions")
        check("무토큰 401", r.status_code == 401, str(r.status_code))

    async with AsyncSessionLocal() as s:
        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
