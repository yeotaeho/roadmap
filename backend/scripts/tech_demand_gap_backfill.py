# KIAT 수요기술 Gap 소규모 백필 — limit 만큼 추출·youth_fit 분포 확인

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config.settings import get_settings  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402
from domain.market_insight.hub.services.tech_demand_gap_service import (  # noqa: E402
    TechDemandGapService,
)


async def main() -> None:
    if not get_settings().openai_api_key:
        print("openai_api_key 없음 — 수요기술 Gap 백필 중단.")
        return
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    window = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    async with AsyncSessionLocal() as session:
        result = await TechDemandGapService(session).refine_and_serve(
            window_days=window, limit=limit
        )
    print(f"백필 결과(limit={limit}, window={window}d): {result}")


if __name__ == "__main__":
    asyncio.run(main())
