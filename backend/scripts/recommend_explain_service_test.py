# RecommendExplainService — FakeLLM 설명 기록·멱등·민감 미주입·dislike 전달 (Neon 통합).

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.market_insight.hub.services.recommend_explain_service import RecommendExplainService

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


async def _seed_cleanup(s, uid: str, slug: str, opp: int) -> None:
    await s.execute(text(
        "DELETE FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
        "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})
    await s.execute(text(
        "DELETE FROM user_chance_matches WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"
    ), {"u": uid, "o": opp})
    await s.execute(text(
        "DELETE FROM user_self_model_evidence WHERE user_id = CAST(:u AS UUID) "
        "AND content IN ('민감한 사정', '야근을 싫어함')"), {"u": uid})
    await s.commit()


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = str((await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).scalar_one())
        slug = (await s.execute(text("SELECT slug FROM sectors ORDER BY slug LIMIT 1"))).scalar_one()
        opp = (await s.execute(text(
            "SELECT id FROM chance_opportunities WHERE is_active = true "
            "AND (d_day_date IS NULL OR d_day_date >= CURRENT_DATE) ORDER BY id LIMIT 1"
        ))).scalar_one()
        await _seed_cleanup(s, uid, slug, opp)

        # 시드 — 설명 NULL 인 오늘 Sync 행 + 매치 행, 민감/비민감 근거.
        # score=100(최댓값) — dev DB 에 같은 사용자의 기존 고득점 행이 있어도
        # TOP_SYNC=3 커트라인 안에 반드시 들도록(동점이면 slug 오름차순이라 알파벳 첫 슬러그도 유리).
        await s.execute(text(
            "INSERT INTO sync_scores_daily (user_id, sector_slug, recorded_date, score, badge) "
            "VALUES (CAST(:u AS UUID), :sl, CURRENT_DATE, 100, '적합')"), {"u": uid, "sl": slug})
        await s.execute(text(
            "INSERT INTO user_chance_matches (user_id, opportunity_id, match_score, match_reason) "
            "VALUES (CAST(:u AS UUID), :o, 80, '의미 유사도 60점') "
            "ON CONFLICT (user_id, opportunity_id) DO UPDATE SET match_score = 80, "
            "match_reason = '의미 유사도 60점', match_explanation = NULL"), {"u": uid, "o": opp})
        # 민감 시드는 화이트리스트 내 dimension('value') + is_sensitive=true 조합 —
        # dimension 필터가 아니라 is_sensitive = false 절만으로 걸러져야 검증이 실효적이다.
        for dim, pol, content, sens in [
            ("dislike", "dislike", "야근을 싫어함", False),
            ("value", None, "민감한 사정", True),
        ]:
            await s.execute(text(
                "INSERT INTO user_self_model_evidence "
                "(user_id, dimension, polarity, content, confidence, is_sensitive, content_hash, source) "
                "VALUES (CAST(:u AS UUID), :d, :p, :c, 0.9, :s, "
                "md5(CAST(:d AS VARCHAR(30)) || COALESCE(CAST(:p AS VARCHAR(10)), '') || :c), 'coach_extraction') "
                "ON CONFLICT (user_id, content_hash) DO NOTHING"
            ), {"u": uid, "d": dim, "p": pol, "c": content, "s": sens})
        await s.commit()

        svc = RecommendExplainService(s)
        svc._api_key = svc._api_key or "test-key"  # 키 부재 환경에서도 FakeLLM 경로 실행
        captured: list[dict] = []

        async def fake_explainer(user_context, sync_items, chance_items):
            captured.append({"ctx": user_context, "sync": sync_items, "chance": chance_items})
            out = {"sync": [], "chance": []}
            for i in sync_items:
                if i["sector_slug"] == slug:
                    out["sync"].append({"sector_slug": slug, "text": "관심과 정렬된 섹터예요."})
            for i in chance_items:
                if i["opportunity_id"] == opp:
                    out["chance"].append({"opportunity_id": opp, "text": "포부와 맞닿은 공고예요."})
            return out

        svc._explainer = fake_explainer
        res = await svc.explain_pending()
        check("처리 성공", res.get("processed", 0) >= 1 and res.get("failed") == 0, str(res))

        v = (await s.execute(text(
            "SELECT explanation FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
            "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})).scalar_one()
        check("sync 설명 기록", v == "관심과 정렬된 섹터예요.", str(v))
        v = (await s.execute(text(
            "SELECT match_explanation FROM user_chance_matches "
            "WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"), {"u": uid, "o": opp})).scalar_one()
        check("chance 설명 기록", v == "포부와 맞닿은 공고예요.", str(v))

        # 프롬프트 컨텍스트 — 민감 미주입·dislike 전달
        blob = json.dumps([c["ctx"] for c in captured], ensure_ascii=False)
        check("민감 근거 미주입", "민감한 사정" not in blob, blob[:200])
        my_ctx = [c["ctx"] for c in captured if "야근을 싫어함" in (c["ctx"].get("dislikes") or [])]
        check("dislike 전달", len(my_ctx) >= 1)

        # 멱등 — 시드 사용자 항목이 다시 대상이 되지 않음
        captured.clear()
        await svc.explain_pending()
        again = [
            c for c in captured
            if any(i.get("sector_slug") == slug for i in c["sync"])
            or any(i.get("opportunity_id") == opp for i in c["chance"])
        ]
        check("멱등(재대상 없음)", len(again) == 0, str(len(again)))

        await _seed_cleanup(s, uid, slug, opp)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
