# AI 상담 SSE 스트리밍 인프로세스 통합 테스트 + 순수 맥락 빌더 검증
#
# 사용법:  python scripts/consult_stream_test.py [user_id]

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SCHEDULER_ENABLED", "false")

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402
from domain.user_intelligence.hub.services.consult_service import build_consult_context  # noqa: E402
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


def test_context_builder() -> None:
    ctx = build_consult_context(
        {
            "persona": {"skills": [{"name": "Python"}], "summary": "ESG×AI 탐색"},
            "roadmap": {"title": "에너지 로드맵"},
            "quests": [{"title": "기초 다지기", "state": "available"}],
            "movers": [{"sector_slug": "ai-data", "score": 88}],
        }
    )
    check("맥락 스킬 포함", "Python" in ctx)
    check("맥락에 로드맵 없음", "로드맵" not in ctx and "에너지 로드맵" not in ctx, ctx)
    check("맥락에 퀘스트 없음", "퀘스트" not in ctx and "기초 다지기" not in ctx, ctx)
    check("맥락 섹터 포함", "ai-data" in ctx)


async def _resolve_user(user_id: str | None) -> str:
    async with AsyncSessionLocal() as s:
        if user_id:
            return user_id
        r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
        if r is None:
            raise SystemExit("users 테이블이 비어 있습니다.")
        return str(r.id)


async def run(user_id: str | None) -> int:
    test_context_builder()

    from main import app

    uid = await _resolve_user(user_id)
    token = JWTService().generate_token(uid, provider="test", email="seed@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as client:
        sr = await client.post("/api/consult/sessions", headers=headers)
        check("세션 생성 200", sr.status_code == 200, str(sr.status_code))
        sid = sr.json().get("sessionId")
        deltas: list[str] = []
        done = False
        async with client.stream(
            "POST", "/api/consult/stream", headers=headers,
            json={"sessionId": sid, "message": "내 로드맵 다음 한 걸음을 한 문장으로 알려줘."},
        ) as resp:
            check("stream 200", resp.status_code == 200, str(resp.status_code))
            ctype = resp.headers.get("content-type", "")
            check("content-type event-stream", "text/event-stream" in ctype, ctype)
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                obj = json.loads(line[5:].strip())
                if obj.get("type") == "delta" and obj.get("content"):
                    deltas.append(obj["content"])
                elif obj.get("type") == "done":
                    done = True
                elif obj.get("type") == "error":
                    check("스트림 에러 없음", False, obj.get("message", ""))
        text_out = "".join(deltas)
        check("delta 토큰 수신", len(deltas) >= 1, f"deltas={len(deltas)}")
        check("done 이벤트 수신", done)
        check("응답 텍스트 비어있지 않음", len(text_out.strip()) > 0)
        print(f"   → deltas={len(deltas)}, 응답 길이={len(text_out)}자")

        # 무토큰 401 (본문은 유효하게 — 인증 실패가 검증보다 먼저 나는지 확인)
        r = await client.post(
            "/api/consult/stream",
            json={"sessionId": "11111111-1111-1111-1111-111111111111", "message": "hi"},
        )
        check("무토큰 401", r.status_code == 401, str(r.status_code))

    # 정리 — 이 사용자 세션·메시지 삭제(스모크가 남긴 데이터 제거).
    async with AsyncSessionLocal() as s:
        await s.execute(
            text(
                "DELETE FROM consult_messages WHERE session_id IN "
                "(SELECT id FROM consult_sessions WHERE user_id = CAST(:u AS UUID))"
            ),
            {"u": uid},
        )
        await s.execute(text("DELETE FROM consult_sessions WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
        await s.commit()

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(asyncio.run(run(arg)))
