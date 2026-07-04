# ConsultService — 스트리밍 영속화·롤링 요약(fake LLM)·소유권. Neon 라운드트립.

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.user_intelligence.hub.repositories.consult_session_repository import ConsultSessionRepository
from domain.user_intelligence.hub.services.consult_service import ConsultService

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
        "DELETE FROM consult_messages WHERE session_id IN "
        "(SELECT id FROM consult_sessions WHERE user_id = CAST(:u AS UUID))"), {"u": uid})
    await s.execute(text("DELETE FROM consult_sessions WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def _drain(gen) -> str:
    out = ""
    async for evt in gen:
        out += evt
    return out


async def fake_planner(coverage, recent, message):
    """SP-8b plan 노드가 실 LLM 을 타지 않게(커버리지가 안 차므로 추출도 안 돈다 — 기존 단정 무영향)."""
    return {"mode": "interview", "newly_covered": [], "focus_axis": "I", "focus_hint": None}


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)
        svc = ConsultService(s)

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
        svc._planner = fake_planner

        sid = await svc.create_session(uid)
        # 스트림 1회 — 사용자+어시스턴트 저장
        await _drain(svc.stream_sse(uid, sid, "안녕"))
        async with AsyncSessionLocal() as s2:
            msgs = await ConsultSessionRepository(s2).fetch_messages(sid)
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
            repo = ConsultSessionRepository(s3)
            for i in range(24):
                await repo.add_message(sid, "user" if i % 2 == 0 else "assistant", f"m{i}")
        await _drain(svc.stream_sse(uid, sid, "요약 트리거"))
        async with AsyncSessionLocal() as s4:
            sess = await ConsultSessionRepository(s4).get_session(sid)
        check("롤링 요약 생성", bool(sess["context_summary"]) and sess["context_summary"].startswith("요약("), str(sess["context_summary"]))
        check("요약 최초 1회 호출", len(older_calls) == 1, str(len(older_calls)))
        first_older_len = len(older_calls[0])

        # 증분 요약 — 메시지 3건 추가 후 재스트리밍하면 새로 밀려난 소수 메시지만 재요약된다.
        async with AsyncSessionLocal() as s6:
            repo6 = ConsultSessionRepository(s6)
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
            check("종료 반영", (await ConsultSessionRepository(s5).get_session(sid))["status"] == "ended")

        # 무키 — API 키 미설정이면 메시지 24개 초과라도 요약 없이 즉시 비활성 폴백.
        svc2 = ConsultService(s)
        svc2._api_key = ""

        async def boom(prior, older):
            raise AssertionError("summarizer must not run without key")

        svc2._summarizer = boom
        svc2._planner = fake_planner
        sid2 = await svc2.create_session(uid)
        async with AsyncSessionLocal() as s7:
            repo7 = ConsultSessionRepository(s7)
            for i in range(26):
                await repo7.add_message(sid2, "user" if i % 2 == 0 else "assistant", f"k{i}")
        out2 = await _drain(svc2.stream_sse(uid, sid2, "질문"))
        check("무키 시 비활성화 폴백 노출", "비활성화" in out2, out2[:200])

        await svc2.end_session(uid, sid2)

        # 요약 실패 — 롱세션(>24)에서 summarizer 가 raise 해도 스트림은 끝까지 완료되고
        # 어시스턴트 응답은 정상 저장된다(best-effort 요약, Codex P2).
        svc3 = ConsultService(s)

        async def raises(prior, older):
            raise RuntimeError("summary down")

        async def fake_streamer3(messages):
            for tok in ["오", "케"]:
                yield tok

        svc3._summarizer = raises
        svc3._streamer = fake_streamer3
        svc3._planner = fake_planner
        sid3 = await svc3.create_session(uid)
        async with AsyncSessionLocal() as s8:
            repo8 = ConsultSessionRepository(s8)
            for i in range(26):
                await repo8.add_message(sid3, "user" if i % 2 == 0 else "assistant", f"r{i}")
        out3 = await _drain(svc3.stream_sse(uid, sid3, "질문"))
        check("요약 실패해도 스트림 완료(done 프레임)", '"type": "done"' in out3, out3[:200])
        async with AsyncSessionLocal() as s9:
            msgs3 = await ConsultSessionRepository(s9).fetch_messages(sid3)
        check("요약 실패해도 어시스턴트 응답 저장", bool(msgs3) and msgs3[-1]["role"] == "assistant", str(msgs3[-3:]))

        await svc3.end_session(uid, sid3)

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
