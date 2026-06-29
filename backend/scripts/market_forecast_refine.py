# 시장 전망 수동/스모크 배치 엔트리 — 실 TimesFM 으로 Silver/Gold 재생성

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import AsyncSessionLocal  # noqa: E402
from domain.market_insight.hub.repositories.forecast_repository import (  # noqa: E402
    ForecastRepository,
)
from domain.market_insight.hub.services.forecast_refine_service import (  # noqa: E402
    MarketForecastRefineService,
)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await MarketForecastRefineService(session).refine_and_serve()
        print("[market_forecast] refine:", result)
        latest = await ForecastRepository(session).fetch_latest_forecast()
        print(f"[market_forecast] 서빙 섹터 {len(latest)}개")
        for row in latest[:12]:
            print(
                f"  {row['sector_slug']:<16} score={row['score']:>3} "
                f"{row['direction_badge']} ret={row['predicted_return_pct']} "
                f"conf={row['confidence']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
