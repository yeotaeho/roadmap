# ConsultService — 스트리밍 영속화·롤링 요약(fake LLM)·소유권. Neon 라운드트립.

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("USER_LLM_PROVIDER", "openai")

import json  # noqa: E402

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

        # 신호 보유 자기모델 → _load_context_system 이 배경 기억 블록을 주입 (monkeypatch)
        from domain.user_intelligence.hub.services import self_model_service as _sms

        async def fake_get_self_model_structured(self, user_id):
            return {
                "riasec": {"top_codes": ["I", "A"]},
                "bigFive": {"scores": {"O": 80, "C": 75, "E": 50, "A": 50, "N": 20}},
                "narrativeSummary": "탐구를 좋아하는 빌더",
            }

        _orig = _sms.SelfModelService.get_self_model_structured
        _sms.SelfModelService.get_self_model_structured = fake_get_self_model_structured
        try:
            sysmsg = await svc._load_context_system(uid)
        finally:
            _sms.SelfModelService.get_self_model_structured = _orig
        check("배경 기억 블록 주입", "배경 기억" in sysmsg and "탐구" in sysmsg, sysmsg[-300:])
        check("서사 포함", "탐구를 좋아하는 빌더" in sysmsg, sysmsg[-300:])

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

        # LLM 설정 오류 — _llm_error 설정 시 메시지 24개 초과라도 요약·스트림 없이 즉시 error SSE(폴백 없음).
        svc2 = ConsultService(s)
        svc2._llm_error = "테스트용 설정 오류"

        async def boom(prior, older):
            raise AssertionError("summarizer must not run when llm error set")

        svc2._summarizer = boom
        svc2._planner = fake_planner
        sid2 = await svc2.create_session(uid)
        async with AsyncSessionLocal() as s7:
            repo7 = ConsultSessionRepository(s7)
            for i in range(26):
                await repo7.add_message(sid2, "user" if i % 2 == 0 else "assistant", f"k{i}")
        out2 = await _drain(svc2.stream_sse(uid, sid2, "질문"))
        evs2 = [json.loads(l[5:]) for l in out2.splitlines() if l.startswith("data:")]
        types2 = [e.get("type") for e in evs2]
        check("_llm_error 시 error SSE(폴백 없음)", "error" in types2 and "delta" not in types2, str(types2))

        await svc2.end_session(uid, sid2)

        # provider=gemini·GEMINI_API_KEY 없음 → stream_sse 가 error SSE(폴백 없음)
        # 주의: `import core.config.settings as _st` 는 core/config/__init__.py 가
        # `from .settings import settings` 로 패키지 속성 core.config.settings 를
        # Settings 인스턴스로 덮어써 버려 _st.get_settings 가 실패한다 — get_settings 직접 import.
        from core.config.settings import get_settings as _get_settings

        _orig_env = (os.environ.get("USER_LLM_PROVIDER"), os.environ.get("GEMINI_API_KEY"))
        os.environ["USER_LLM_PROVIDER"] = "gemini"
        # .env 에 실키가 있으면 pop 만으로는 dotenv 소스로 폴백돼 키가 살아있다(env var > dotenv 우선순위) — 빈 문자열로 명시 오버라이드.
        os.environ["GEMINI_API_KEY"] = ""
        _get_settings.cache_clear()
        try:
            svc_err = ConsultService(s)
            sid_err = await svc_err.get_or_create_session(uid)
            out_err = await _drain(svc_err.stream_sse(uid, sid_err, "안녕"))
            evs_err = [json.loads(l[5:]) for l in out_err.splitlines() if l.startswith("data:")]
            types_err = [e.get("type") for e in evs_err]
            check("gemini 키없음 → error SSE", "error" in types_err and "delta" not in types_err, str(types_err))
            await svc_err.end_session(uid, sid_err)
        finally:
            if _orig_env[0] is not None:
                os.environ["USER_LLM_PROVIDER"] = _orig_env[0]
            else:
                os.environ.pop("USER_LLM_PROVIDER", None)
            if _orig_env[1] is not None:
                os.environ["GEMINI_API_KEY"] = _orig_env[1]
            else:
                os.environ.pop("GEMINI_API_KEY", None)
            _get_settings.cache_clear()

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
