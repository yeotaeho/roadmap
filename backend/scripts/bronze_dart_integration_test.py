"""로컬 통합 점검: `raw_economic_data`에 DART Bronze 적재.

사전 조건:
  - Alembic 마이그레이션 적용 (`alembic upgrade head`)
  - 환경 변수: `NEON_DATABASE_URL`, `DART_API_KEY` 또는 `OPENDART_API_KEY`

실행 (backend 디렉터리에서):

  python scripts/bronze_dart_integration_test.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# backend/ 를 import 루트로
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


async def _run() -> int:
    from core.config.settings import get_settings
    from core.database import AsyncSessionLocal
    from domain.master.hub.services.bronze_economic_ingest_service import BronzeEconomicIngestService

    settings = get_settings()
    if not settings.dart_api_key:
        print("[SKIP] DART_API_KEY 또는 OPENDART_API_KEY 가 설정되어 있지 않습니다.")
        return 1

    async with AsyncSessionLocal() as session:
        service = BronzeEconomicIngestService(session, settings.dart_api_key)
        result = await service.ingest_dart()
        print("[OK]", result)
        if counts := result.get("source_type_counts"):
            print("[STATS] source_type 분포:", counts)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
