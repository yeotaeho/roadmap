# SelfModelExtractionService — 세션→자기모델 추출·멱등·MIN_NEW 스킵(fake extractor, Neon)

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.user_intelligence.hub.repositories.consult_session_repository import ConsultSessionRepository
from domain.user_intelligence.hub.services.self_model_extraction_service import SelfModelExtractionService
from domain.user_intelligence.hub.services.self_model_service import SelfModelService

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
    await s.execute(text("DELETE FROM user_self_model_evidence WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)
        repo = ConsultSessionRepository(s)
        sid = await repo.create_session(uid)
        for i in range(8):
            await repo.add_message(sid, "user" if i % 2 == 0 else "assistant", f"발표와 데이터 분석 이야기 {i}")

        svc = SelfModelExtractionService(s)
        fake_calls = {"n": 0}

        async def fake_extractor(messages):
            fake_calls["n"] += 1
            return {
                "riasec_scores": {"R": 50, "I": 88, "A": 82, "S": 50, "E": 55, "C": 45},
                "riasec_axis_confidence": {"R": 0.2, "I": 0.9, "A": 0.8, "S": 0.2, "E": 0.3, "C": 0.2},
                "narrative": "탐구·표현 지향",
                "evidence": [
                    {"dimension": "like", "polarity": "like", "content": "발표를 좋아함", "confidence": 0.9, "is_sensitive": False},
                    {"dimension": "constraint", "polarity": None, "content": "장거리 통근 어려움", "confidence": 0.7, "is_sensitive": True},
                ],
            }

        svc._extractor = fake_extractor

        res = await svc.extract_session(uid, sid)
        check("추출 8건", res.get("extracted") == 8, str(res))
        check("근거 2건", res.get("evidence") == 2, str(res))

        model = await SelfModelService(s).get_self_model(uid, include_sensitive=True)
        riasec = model["riasec"]
        check("riasec scores 존재", isinstance(riasec, dict) and "scores" in riasec, str(riasec))
        check("riasec I 최상위 근접", riasec["scores"]["I"] >= riasec["scores"]["R"], str(riasec["scores"]))
        check("narrative 반영", model["narrativeSummary"] == "탐구·표현 지향")
        contents = [e["content"] for e in model["evidence"]]
        check("비민감 근거 저장", "발표를 좋아함" in contents)
        check("민감 근거 격리 저장", "장거리 통근 어려움" in contents)  # include_sensitive=True 이므로 보임

        # extracted_until 전진
        check("extracted_until=8", (await repo.get_session(sid))["extracted_until"] == 8)

        # 멱등 — 새 메시지 없으면 스킵, 추출기 재호출 안 됨
        res2 = await svc.extract_session(uid, sid)
        check("재추출 스킵", res2.get("skipped") is True, str(res2))
        check("추출기 1회만 호출", fake_calls["n"] == 1, str(fake_calls))

        # narrative-only(RIASEC 신호 없음) 세션 — 서사가 riasec_confidence=0 에도 불구하고 기록되어야 함.
        sid_narr = await repo.create_session(uid)
        for i in range(8):
            await repo.add_message(sid_narr, "user" if i % 2 == 0 else "assistant", f"가치관 이야기 {i}")

        async def narrative_only_extractor(messages):
            return {
                "riasec_scores": {c: 50 for c in ("R", "I", "A", "S", "E", "C")},
                "riasec_axis_confidence": {c: 0.0 for c in ("R", "I", "A", "S", "E", "C")},
                "narrative": "안정보다 성장을 우선시함",
                "evidence": [],
            }

        svc._extractor = narrative_only_extractor
        res_narr = await svc.extract_session(uid, sid_narr)
        check("narrative-only 추출 처리", res_narr.get("extracted") == 8, str(res_narr))
        model_narr = await SelfModelService(s).get_self_model(uid, include_sensitive=True)
        check("riasec 없어도 narrative 기록됨", model_narr["narrativeSummary"] == "안정보다 성장을 우선시함", str(model_narr))

        # MIN_NEW 미만 — 3개만 더 추가(신규 3 < 6) → 스킵
        for i in range(3):
            await repo.add_message(sid, "user", f"추가 {i}")
        res3 = await svc.extract_session(uid, sid)
        check("MIN_NEW 미만 스킵", res3.get("skipped") is True, str(res3))

        # extract_pending — 6개 더 추가하면 신규 9 → 선택·처리
        for i in range(6):
            await repo.add_message(sid, "user", f"더 {i}")
        pend = await svc.extract_pending(limit=10)
        check("extract_pending 처리", pend.get("processed") >= 1, str(pend))

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
