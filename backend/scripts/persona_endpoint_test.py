# 페르소나 엔드포인트 인프로세스 통합 테스트 — GET/PUT 라운드트립
#
# 사용법:  python scripts/persona_endpoint_test.py [user_id]

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

    payload = {
        "skills": [{"name": "Python", "level": "중급"}, {"name": "SQL", "level": "입문"}],
        "experiences": [{"title": "데이터 동아리", "description": "공공데이터 시각화", "period": "2025"}],
        "education": [{"school": "OO대", "major": "컴퓨터공학", "degree": "학사", "status": "재학"}],
        "summary": "엔드포인트 테스트 페르소나",
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/persona", headers=headers)
        check("GET 200", r.status_code == 200, str(r.status_code))
        check("GET success", r.json().get("success") is True)

        r = await client.put("/api/persona", headers=headers, json=payload)
        check("PUT 200", r.status_code == 200, str(r.status_code))
        saved = r.json().get("persona", {})
        check("PUT source=user_form", saved.get("source") == "user_form", str(saved.get("source")))

        r = await client.get("/api/persona", headers=headers)
        p = r.json().get("persona", {})
        check("스킬 2개 반영", len(p.get("skills", [])) == 2, str(p.get("skills")))
        check("스킬 레벨 보존", p.get("skills", [{}])[0].get("level") == "중급")
        check("학력 반영", (p.get("education") or [{}])[0].get("major") == "컴퓨터공학")
        check("요약 반영", p.get("summary") == "엔드포인트 테스트 페르소나")

        r = await client.get("/api/persona")
        check("무토큰 401", r.status_code == 401, str(r.status_code))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(asyncio.run(run(arg)))
