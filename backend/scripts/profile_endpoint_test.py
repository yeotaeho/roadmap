# 기본정보 엔드포인트 인프로세스 통합 테스트 — GET/PUT 라운드트립

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
        "birthYear": 1999,
        "gender": "male",
        "region": "서울",
        "currentStatus": "job_seeking",
        "educationLevel": "bachelor",
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/user/profile", headers=headers)
        check("GET 200", r.status_code == 200, str(r.status_code))
        check("GET success", r.json().get("success") is True)

        r = await client.put("/api/user/profile", headers=headers, json=payload)
        check("PUT 200", r.status_code == 200, str(r.status_code))
        saved = r.json().get("profile", {})
        check("PUT source=user_form", saved.get("source") == "user_form", str(saved.get("source")))

        r = await client.get("/api/user/profile", headers=headers)
        p = r.json().get("profile", {})
        check("birthYear 반영", p.get("birthYear") == 1999, str(p.get("birthYear")))
        check("region 반영", p.get("region") == "서울")
        check("currentStatus 반영", p.get("currentStatus") == "job_seeking")

        # 부분 입력(전부 nullable) — gender 만 None 으로 덮어쓰기 가능
        r = await client.put(
            "/api/user/profile", headers=headers,
            json={"birthYear": 1999, "region": "서울", "currentStatus": "job_seeking", "educationLevel": "bachelor"},
        )
        p = (await client.get("/api/user/profile", headers=headers)).json().get("profile", {})
        check("gender null 허용", p.get("gender") is None, str(p.get("gender")))

        # 출생연도 범위초과(생년월일 8자리 오입력) → 500 아닌 422 검증
        r = await client.put(
            "/api/user/profile", headers=headers, json={"birthYear": 20040813},
        )
        check("birthYear 범위초과 422", r.status_code == 422, str(r.status_code))
        # 미래 연도(SMALLINT 범위 내지만 현재연도 초과) → 422 (웹 외 클라이언트 방어)
        r = await client.put(
            "/api/user/profile", headers=headers, json={"birthYear": 3000},
        )
        check("birthYear 미래연도 422", r.status_code == 422, str(r.status_code))
        # region 길이초과(VARCHAR 50) → 500 아닌 422
        r = await client.put(
            "/api/user/profile", headers=headers, json={"region": "가" * 60},
        )
        check("region 길이초과 422", r.status_code == 422, str(r.status_code))
        # 유효 연도는 정상 저장(직전 값 보존 확인)
        p = (await client.get("/api/user/profile", headers=headers)).json().get("profile", {})
        check("범위초과 거부 후 기존값 유지", p.get("birthYear") == 1999, str(p.get("birthYear")))

        r = await client.get("/api/user/profile")
        check("무토큰 401", r.status_code == 401, str(r.status_code))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
