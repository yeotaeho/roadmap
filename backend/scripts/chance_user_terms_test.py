# Chance user_terms 성향·스펙 가산 통합 테스트 — fetch_users 컬럼 + 매칭 스모크

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402
from domain.market_insight.hub.repositories.chance_repository import ChanceRepository  # noqa: E402
from domain.market_insight.hub.services.user_embed_text import disposition_spec_terms  # noqa: E402

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


async def run() -> int:
    async with AsyncSessionLocal() as s:
        r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
        if r is None:
            raise SystemExit("users 테이블이 비어 있습니다.")
        uid = str(r.id)
        # 시드 사용자에 sync_profile + 성향 보장.
        await s.execute(
            text(
                """
                INSERT INTO user_sync_profiles (user_id, target_job, interest_keywords, updated_at)
                VALUES (CAST(:uid AS UUID), '백엔드', CAST('["AI"]' AS JSONB), now())
                ON CONFLICT (user_id) DO UPDATE SET updated_at = now()
                """
            ),
            {"uid": uid},
        )
        await s.execute(
            text(
                """
                INSERT INTO user_preferences (user_id, work_style, work_values, source, updated_at)
                VALUES (CAST(:uid AS UUID), 'challenge', CAST('["growth"]' AS JSONB), 'user_form', now())
                ON CONFLICT (user_id) DO UPDATE SET work_style = 'challenge', work_values = CAST('["growth"]' AS JSONB), updated_at = now()
                """
            ),
            {"uid": uid},
        )
        await s.commit()

        repo = ChanceRepository(s)
        users = await repo.fetch_users()
        check("fetch_users 비어있지 않음", len(users) >= 1)
        check("fetch_users 컬럼: work_style", hasattr(users[0], "work_style"))
        check("fetch_users 컬럼: skills", hasattr(users[0], "skills"))
        seed = [u for u in users if str(u.user_id) == uid]
        check("시드 사용자 포함", len(seed) == 1)
        u = seed[0]
        terms = disposition_spec_terms(
            u.work_style, u.company_size_pref, u.work_type_pref, u.work_values,
            u.skills, u.certifications, u.languages, u.projects,
        )
        check("성향 용어 가산(도전 지향)", "도전 지향" in terms, str(terms))
        check("가치 용어 가산(성장)", "성장" in terms)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
