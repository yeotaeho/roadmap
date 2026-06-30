# 사용자 재임베딩 선택·직렬화 통합 테스트 — 데이터 변경 시 미임베딩 큐에 재진입하는지

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text  # noqa: E402

from core.config.settings import get_settings  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402
from domain.market_insight.hub.repositories.embed_repository import EmbedRepository  # noqa: E402
from domain.market_insight.hub.services.embed_service import UserEmbedService  # noqa: E402

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


async def _seed_user(s) -> str:
    r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
    if r is None:
        raise SystemExit("users 테이블이 비어 있습니다.")
    uid = str(r.id)
    # 시드 사용자에 sync_profile 보장(없으면 생성).
    await s.execute(
        text(
            """
            INSERT INTO user_sync_profiles (user_id, target_job, interest_keywords, updated_at)
            VALUES (CAST(:uid AS UUID), :job, CAST(:kw AS JSONB), now())
            ON CONFLICT (user_id) DO UPDATE SET target_job = EXCLUDED.target_job, updated_at = now()
            """
        ),
        {"uid": uid, "job": "백엔드 엔지니어", "kw": '["AI"]'},
    )
    await s.commit()
    return uid


async def run() -> int:
    settings = get_settings()
    model = settings.llm_embed_model

    async with AsyncSessionLocal() as s:
        uid = await _seed_user(s)
        repo = EmbedRepository(s)

        # Part A — fetch 가 신규 컬럼을 반환하는가(DB-only).
        rows = await repo.fetch_unembedded_users(model, 300)
        seed_rows = [r for r in rows if str(r.user_id) == uid]
        # 시드 사용자가 (임베딩 없거나 방금 sync 갱신으로) 큐에 있어야 한다.
        check("fetch 컬럼: work_style", hasattr(rows[0] if rows else seed_rows[0], "work_style"))
        check("fetch 컬럼: skills", hasattr(rows[0] if rows else seed_rows[0], "skills"))
        check("fetch 컬럼: source_version", hasattr(rows[0] if rows else seed_rows[0], "source_version"))

        # Part B — 성향 변경 후 재선택되는가(DB-only).
        await s.execute(
            text(
                """
                INSERT INTO user_preferences (user_id, work_style, source, updated_at)
                VALUES (CAST(:uid AS UUID), 'challenge', 'user_form', now())
                ON CONFLICT (user_id) DO UPDATE SET work_style = 'challenge', updated_at = now()
                """
            ),
            {"uid": uid},
        )
        await s.commit()
        rows2 = await repo.fetch_unembedded_users(model, 300)
        check("성향 변경 후 재선택", any(str(r.user_id) == uid for r in rows2), f"uid={uid}")
        sel = [r for r in rows2 if str(r.user_id) == uid][0]
        check("재선택 행 work_style=challenge", sel.work_style == "challenge", str(sel.work_style))

    # Part C — OpenAI 키 있으면 실제 재임베딩 사이클(없으면 skip).
    if settings.openai_api_key:
        async with AsyncSessionLocal() as s:
            svc = UserEmbedService(s)
            res = await svc.embed_users(limit=300)
            check("embed_users scanned>=1", res["scanned"] >= 1, str(res))
            repo = EmbedRepository(s)
            rows3 = await repo.fetch_unembedded_users(model, 300)
            check("임베딩 후 시드 미선택(멱등)", all(str(r.user_id) != uid for r in rows3), f"uid={uid}")
    else:
        print("[SKIP] OPENAI_API_KEY 없음 -- Part C(실제 임베딩) 생략")

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
