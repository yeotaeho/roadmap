# Roadmap 엔드포인트 인프로세스 통합 테스트 — 마이그레이션·시드 적용 후 실행
#
# 전제: c4e7a9d2f6b1 마이그레이션 적용 + seed_roadmap_mock.py 시드 완료.
# 사용법:  python scripts/roadmap_endpoint_test.py [user_id]
#   user_id 생략 시 users 첫 사용자로 토큰을 발급한다.

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
    from main import app  # 라우터 등록 검증 겸

    uid = await _resolve_user(user_id)
    token = JWTService().generate_token(uid, provider="test", email="seed@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1) 여정
        r = await client.get("/api/roadmap/journey", headers=headers)
        check("journey 200", r.status_code == 200, str(r.status_code))
        body = r.json()
        check("journey success", body.get("success") is True)
        tree = body.get("questTree")
        check("questTree 루트 존재", bool(tree) and tree.get("id") == "root", str(tree)[:80])
        if tree:
            check("루트 children 2개", len(tree.get("children", [])) == 2)
            rm = body.get("roadmap") or {}
            check("skillPillars 3축", len(rm.get("skillPillars") or []) == 3)
            check("bridgeKeywords 존재", len(rm.get("bridgeKeywords") or []) >= 1)

        # 2) 아카이브 조회(시드 월)
        r = await client.get("/api/roadmap/archive?month=2026-04", headers=headers)
        check("archive 200", r.status_code == 200, str(r.status_code))
        logs = r.json().get("logs", {})
        check("아카이브 시드 2일 존재", "2026-04-22" in logs and "2026-04-26" in logs, str(list(logs)))

        # 3) 일별 upsert → 재조회 반영
        r = await client.put(
            "/api/roadmap/archive/2026-06-28",
            headers=headers,
            json={"completedQuestIds": ["q-carbon-schema"], "note": "엔드포인트 테스트 기록"},
        )
        check("archive PUT 200", r.status_code == 200, str(r.status_code))
        r = await client.get("/api/roadmap/archive?month=2026-06", headers=headers)
        day = r.json().get("logs", {}).get("2026-06-28")
        check("upsert 반영", bool(day) and day.get("completedQuestIds") == ["q-carbon-schema"], str(day))

        # 4) 인증 없으면 401
        r = await client.get("/api/roadmap/journey")
        check("무토큰 401", r.status_code == 401, str(r.status_code))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(asyncio.run(run(arg)))
