# /api/roadmap/refine 인프로세스 통합 테스트 — 생성 → 여정 반영(LLM 또는 템플릿)
#
# 사용법:  python scripts/roadmap_refine_test.py [user_id]
#   OPENAI_API_KEY 있으면 LLM 생성, 없으면 템플릿 폴백 경로를 검증한다.

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


async def _resolve_user(user_id: str | None) -> str:
    async with AsyncSessionLocal() as s:
        if user_id:
            return user_id
        r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
        if r is None:
            raise SystemExit("users 테이블이 비어 있습니다.")
        return str(r.id)


async def run(user_id: str | None) -> int:
    from main import app

    uid = await _resolve_user(user_id)
    token = JWTService().generate_token(uid, provider="test", email="seed@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as client:
        r = await client.post("/api/roadmap/refine", headers=headers)
        check("refine 200", r.status_code == 200, str(r.status_code))
        body = r.json()
        check("refine success", body.get("success") is True)
        check("source llm|template", body.get("source") in ("llm", "template"), str(body.get("source")))
        check("퀘스트 생성됨(>=4)", (body.get("quest_count") or 0) >= 4, str(body.get("quest_count")))
        print(f"   → source={body.get('source')}, quests={body.get('quest_count')}")

        r = await client.get("/api/roadmap/journey", headers=headers)
        tree = r.json().get("questTree")
        check("여정에 생성 트리 반영", bool(tree) and tree.get("id") == "root", str(tree)[:80])
        check("루트 자식 존재", bool(tree) and len(tree.get("children", [])) >= 1)

        r = await client.post("/api/roadmap/refine")
        check("무토큰 401", r.status_code == 401, str(r.status_code))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(asyncio.run(run(arg)))
