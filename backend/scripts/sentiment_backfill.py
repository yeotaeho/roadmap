# 기존 분류행(sentiment NULL)에 LLM 감성을 재추출해 채우는 백필 (멱등 — sentiment NULL 만 대상)

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config.settings import get_settings  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402
from core.llm.client import LlmClient  # noqa: E402
from domain.market_insight.hub.repositories.pulse_repository import PulseRepository  # noqa: E402
from domain.market_insight.hub.services.text_sector_classify_service import (  # noqa: E402
    CLASSIFY_CHUNK,
    MAX_INPUT_CHARS,
    PROMPT_VERSION,
    SECTOR_SLUGS,
    _TARGET_TABLES,
)


async def count_only(window_days: int) -> None:
    """LLM 호출 없이 백필 대상 건수만 테이블별로 보고한다(토큰 0)."""
    async with AsyncSessionLocal() as session:
        repo = PulseRepository(session)
        total = 0
        for table_ref in _TARGET_TABLES:
            rows = await repo.fetch_rows_needing_sentiment(table_ref, PROMPT_VERSION, window_days, 100000)
            total += len(rows)
            print(f"  {table_ref}: {len(rows)}")
        print(f"[COUNT] window={window_days}d  sentiment NULL 대상 합계 = {total}")


async def run(window_days: int, limit: int) -> None:
    """대상 행을 재분류해 sentiment·sentiment_score 만 UPDATE 한다. 청크마다 커밋."""
    settings = get_settings()
    llm = LlmClient(api_key=settings.openai_api_key, model=settings.llm_classify_model)
    scanned = 0
    updated = 0
    async with AsyncSessionLocal() as session:
        repo = PulseRepository(session)
        for table_ref in _TARGET_TABLES:
            rows = await repo.fetch_rows_needing_sentiment(table_ref, PROMPT_VERSION, window_days, limit)
            print(f"{table_ref}: {len(rows)} rows")
            payload: list[dict] = []
            for class_id, body in rows:
                scanned += 1
                text_in = (body or "").strip()[:MAX_INPUT_CHARS]
                res = await llm.classify_sector(text_in, SECTOR_SLUGS)
                payload.append(
                    {
                        "class_id": class_id,
                        "sentiment": res.get("sentiment"),
                        "sentiment_score": res.get("sentiment_score"),
                    }
                )
                if len(payload) >= CLASSIFY_CHUNK:
                    updated += await repo.update_sentiment(payload)
                    await session.commit()
                    payload = []
                    print(f"  ...{updated} updated")
            if payload:
                updated += await repo.update_sentiment(payload)
                await session.commit()
    print(f"[DONE] scanned={scanned} updated={updated}")


def main() -> int:
    window_days = 30
    if len(sys.argv) > 1 and sys.argv[1] == "count":
        asyncio.run(count_only(window_days))
        return 0
    if len(sys.argv) > 1:
        window_days = int(sys.argv[1])
    asyncio.run(run(window_days, limit=100000))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
