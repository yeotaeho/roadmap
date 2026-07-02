# 설명 무효화 — upsert 시 입력 불변이면 설명 보존, 변경이면 NULL (Neon 통합).

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.market_insight.hub.repositories.chance_repository import ChanceRepository
from domain.market_insight.hub.repositories.embed_repository import EmbedRepository
from domain.market_insight.hub.repositories.sync_repository import SyncRepository

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
        slug = (await s.execute(text("SELECT slug FROM sectors ORDER BY slug LIMIT 1"))).scalar_one()
        opp = (await s.execute(text(
            "SELECT id FROM chance_opportunities WHERE is_active = true ORDER BY id LIMIT 1"
        ))).scalar_one()

        # 시드 정리(재실행 안전)
        await s.execute(text(
            "DELETE FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
            "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})
        await s.execute(text(
            "DELETE FROM user_chance_matches WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"
        ), {"u": uid, "o": opp})
        await s.commit()

        sync_repo = SyncRepository(s)
        chance_repo = ChanceRepository(s)

        # Sync — 설명 부여 후 동일 upsert 는 보존, 점수 변경은 NULL
        await sync_repo.upsert_sync_gold(uid, slug, 72, "적합")
        await s.execute(text(
            "UPDATE sync_scores_daily SET explanation = '테스트 설명' "
            "WHERE user_id = CAST(:u AS UUID) AND sector_slug = :sl AND recorded_date = CURRENT_DATE"
        ), {"u": uid, "sl": slug})
        await s.commit()
        await sync_repo.upsert_sync_gold(uid, slug, 72, "적합")
        await s.commit()
        v = (await s.execute(text(
            "SELECT explanation FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
            "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})).scalar_one()
        check("sync 불변 → 설명 보존", v == "테스트 설명", str(v))
        await sync_repo.upsert_sync_gold(uid, slug, 80, "강한 적합")
        await s.commit()
        v = (await s.execute(text(
            "SELECT explanation FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
            "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})).scalar_one()
        check("sync 변경 → 설명 NULL", v is None, str(v))

        # fetch_scores 에 explanation 키 노출
        scores = await sync_repo.fetch_scores(uid)
        check("fetch_scores 키", all("explanation" in r for r in scores), str(scores[:1]))

        # Chance — 동일 패턴
        await chance_repo.upsert_match(uid, opp, 80, "테스트 사유")
        await s.execute(text(
            "UPDATE user_chance_matches SET match_explanation = '매칭 설명' "
            "WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"), {"u": uid, "o": opp})
        await s.commit()
        await chance_repo.upsert_match(uid, opp, 80, "테스트 사유")
        await s.commit()
        v = (await s.execute(text(
            "SELECT match_explanation FROM user_chance_matches "
            "WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"), {"u": uid, "o": opp})).scalar_one()
        check("chance 불변 → 설명 보존", v == "매칭 설명", str(v))
        await chance_repo.upsert_match(uid, opp, 55, "다른 사유")
        await s.commit()
        v = (await s.execute(text(
            "SELECT match_explanation FROM user_chance_matches "
            "WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"), {"u": uid, "o": opp})).scalar_one()
        check("chance 변경 → 설명 NULL", v is None, str(v))

        matches = await chance_repo.fetch_matches(uid)
        check("fetch_matches 키", all("match_explanation" in r for r in matches), str(matches[:1]))

        # 임베딩 실갱신(개인화 컨텍스트 변경) 시 사용자 매치 설명 무효화
        await s.execute(text(
            "UPDATE user_chance_matches SET match_explanation = '컨텍스트 변경 전 설명' "
            "WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"), {"u": uid, "o": opp})
        await s.commit()
        cleared = await EmbedRepository(s).clear_user_match_explanations(uid)
        await s.commit()
        v = (await s.execute(text(
            "SELECT match_explanation FROM user_chance_matches "
            "WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"), {"u": uid, "o": opp})).scalar_one()
        check("임베딩 갱신 → 설명 무효화", cleared >= 1 and v is None, f"cleared={cleared} v={v}")

        # 동일 무효화의 Sync 대칭 — 당일 행 설명 클리어
        await s.execute(text(
            "UPDATE sync_scores_daily SET explanation = '컨텍스트 변경 전 설명' "
            "WHERE user_id = CAST(:u AS UUID) AND sector_slug = :sl AND recorded_date = CURRENT_DATE"
        ), {"u": uid, "sl": slug})
        await s.commit()
        cleared_sync = await EmbedRepository(s).clear_user_sync_explanations(uid)
        await s.commit()
        v = (await s.execute(text(
            "SELECT explanation FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
            "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})).scalar_one()
        check("임베딩 갱신 → 당일 sync 설명 무효화", cleared_sync >= 1 and v is None, f"cleared={cleared_sync} v={v}")

        # 시드 정리
        await s.execute(text(
            "DELETE FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
            "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})
        await s.execute(text(
            "DELETE FROM user_chance_matches WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"
        ), {"u": uid, "o": opp})
        await s.commit()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
