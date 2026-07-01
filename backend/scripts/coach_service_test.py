# CoachService — 스트리밍 영속화·롤링 요약(fake LLM)·소유권. Neon 라운드트립.

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository
from domain.ai_coach.hub.services.coach_service import CoachService

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


async def _drain(gen) -> str:
    out = ""
    async for evt in gen:
        out += evt
    return out


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)
        svc = CoachService(s)

        # fake 주입 — 스트림은 고정 토큰, 요약은 고정 문자열
        captured = {}
        async def fake_streamer(messages):
            captured["messages"] = messages
            for tok in ["안", "녕", "하세요"]:
                yield tok

        older_calls = []

        async def fake_summarizer(prior, older):
            older_calls.append(older)
            return f"요약({len(older)}건)"

        svc._streamer = fake_streamer
        svc._summarizer = fake_summarizer

        sid = await svc.create_session(uid)
        # 스트림 1회 — 사용자+어시스턴트 저장
        await _drain(svc.stream_sse(uid, sid, "안녕"))
        async with AsyncSessionLocal() as s2:
            msgs = await CoachSessionRepository(s2).fetch_messages(sid)
        check("user+assistant 저장", [m["role"] for m in msgs] == ["user", "assistant"], str(msgs))
        check("assistant 누적 저장", msgs[1]["content"] == "안녕하세요", msgs[1]["content"])
        sys_msgs = [m for m in captured.get("messages", []) if m["role"] == "system"]
        check("맥락 주입됨", any("[사용자 맥락]" in m["content"] for m in sys_msgs), str(sys_msgs)[:200])

        # 소유권 — 타인 uuid
        import uuid as _u
        try:
            await svc.verify_owner(str(_u.uuid4()), sid)
            check("타인 접근 거부", False, "no raise")
        except PermissionError:
            check("타인 접근 PermissionError", True)

        # 롤링 요약 — 임계(24)까지 채운 뒤 스트림 → 요약 생성
        async with AsyncSessionLocal() as s3:
            repo = CoachSessionRepository(s3)
            for i in range(24):
                await repo.add_message(sid, "user" if i % 2 == 0 else "assistant", f"m{i}")
        await _drain(svc.stream_sse(uid, sid, "요약 트리거"))
        async with AsyncSessionLocal() as s4:
            sess = await CoachSessionRepository(s4).get_session(sid)
        check("롤링 요약 생성", bool(sess["context_summary"]) and sess["context_summary"].startswith("요약("), str(sess["context_summary"]))
        check("요약 최초 1회 호출", len(older_calls) == 1, str(len(older_calls)))
        first_older_len = len(older_calls[0])

        # 증분 요약 — 메시지 3건 추가 후 재스트리밍하면 새로 밀려난 소수 메시지만 재요약된다.
        async with AsyncSessionLocal() as s6:
            repo6 = CoachSessionRepository(s6)
            for i in range(3):
                await repo6.add_message(sid, "user" if i % 2 == 0 else "assistant", f"n{i}")
        await _drain(svc.stream_sse(uid, sid, "증분 트리거"))
        check("요약 2회째 호출", len(older_calls) == 2, str(len(older_calls)))
        second_older_len = len(older_calls[1]) if len(older_calls) > 1 else -1
        check(
            "증분 요약은 소수 메시지만 재요약",
            0 < second_older_len < first_older_len,
            f"first={first_older_len} second={second_older_len}",
        )

        # 재개 — 최근 active 세션이 있으면 새로 만들지 않고 이어간다.
        sid2 = await svc.get_or_create_session(uid)
        check("세션 재개(get-or-create)", sid2 == sid, f"sid={sid} sid2={sid2}")

        await svc.end_session(uid, sid)
        async with AsyncSessionLocal() as s5:
            check("종료 반영", (await CoachSessionRepository(s5).get_session(sid))["status"] == "ended")

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
