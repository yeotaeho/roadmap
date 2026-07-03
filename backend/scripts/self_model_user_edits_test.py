# 사용자 자기모델 편집 — 레벨→점수·정서안정성 flip·축별 provenance·auto 해제 (Neon 통합).

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
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


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = str((await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).scalar_one())
        prev = (await s.execute(text(
            "SELECT riasec, big_five, narrative_summary, axis_confidence, source, axis_source "
            "FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})).first()
        row_existed = prev is not None
        snap = dict(prev._mapping) if prev is not None else None

        svc = SelfModelService(s)

        # 편집 — riasec 확정(I 높음), big_five 확정(정서안정성 높음 → N 낮음), 서사
        model = await svc.apply_user_edits(uid, {
            "riasec": {"levels": {"R": "low", "I": "high", "A": "mid", "S": "low", "E": "mid", "C": "low"}},
            "big_five": {"levels": {"O": "high", "C": "high", "E": "mid", "A": "mid", "stability": "high"}},
            "narrative": "탐구를 좋아하는 빌더",
        })
        check("riasec I 점수 75", model["riasec"]["scores"]["I"] == 75, str(model["riasec"]["scores"]))
        check("riasec top_codes I", "I" in (model["riasec"]["top_codes"] or []), str(model["riasec"]["top_codes"]))
        check("정서안정성 flip → N 25", model["bigFive"]["scores"]["N"] == 25, str(model["bigFive"]["scores"]))
        check("big_five O 75", model["bigFive"]["scores"]["O"] == 75)
        check("서사 반영", model["narrativeSummary"] == "탐구를 좋아하는 빌더")
        check("axisSource riasec·big_five·narrative user_form",
              (model["axisSource"] or {}).get("riasec") == "user_form"
              and (model["axisSource"] or {}).get("big_five") == "user_form"
              and (model["axisSource"] or {}).get("narrative_summary") == "user_form", str(model["axisSource"]))

        # user_form 축은 코치 추출이 잠식 안 함
        from domain.user_intelligence.hub.services.self_model_service import merge_structured
        existing = await svc.repo.fetch_self_model(uid)
        merged = merge_structured(existing, {
            "riasec": {"window_scores": {c: 95 for c in "RIASEC"}, "window_conf": {c: 0.9 for c in "RIASEC"}},
            "big_five": None, "narrative_summary": None,
            "axis_confidence": {"riasec": 0.9},
        }, "consult_extraction")
        check("추출이 user_form riasec 보존", merged["riasec"]["scores"]["I"] == 75, str(merged["riasec"]["scores"]))

        # auto — riasec 을 AI 에게 반환
        model2 = await svc.apply_user_edits(uid, {"riasec": "auto"})
        check("auto → axisSource riasec 제거", "riasec" not in (model2["axisSource"] or {}), str(model2["axisSource"]))

        # 원상 복원(데이터 파괴 방지)
        if row_existed:
            await s.execute(text(
                "UPDATE user_self_model SET riasec = CAST(:r AS JSONB), big_five = CAST(:b AS JSONB), "
                "narrative_summary = :n, axis_confidence = CAST(:ac AS JSONB), source = :src, "
                "axis_source = CAST(:asrc AS JSONB), updated_at = now() WHERE user_id = CAST(:u AS UUID)"
            ), {"u": uid,
                "r": json.dumps(snap["riasec"]) if snap["riasec"] is not None else None,
                "b": json.dumps(snap["big_five"]) if snap["big_five"] is not None else None,
                "n": snap["narrative_summary"],
                "ac": json.dumps(snap["axis_confidence"]) if snap["axis_confidence"] is not None else None,
                "src": snap["source"],
                "asrc": json.dumps(snap["axis_source"]) if snap["axis_source"] is not None else None})
        else:
            await s.execute(text("DELETE FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
        await s.commit()

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
