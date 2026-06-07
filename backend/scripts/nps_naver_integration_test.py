"""국민연금 포트폴리오 통합 테스트 (라이브 + DB).

실행: python scripts/nps_naver_integration_test.py
요구:
  - .env 의 DATABASE_URL, DART_API_KEY (NPS)
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.config.settings import get_settings  # noqa: E402
from core.database import get_db  # noqa: E402
from domain.master.hub.services.bronze_economic_ingest_service import (  # noqa: E402
    BronzeEconomicIngestService,
)


async def test_nps_portfolio() -> None:
    print("\n" + "=" * 80)
    print("국민연금 포트폴리오 (DART 지분공시) 통합 테스트")
    print("=" * 80 + "\n")

    settings = get_settings()
    if not settings.dart_api_key:
        print("[SKIP] DART_API_KEY 없음")
        return

    kst = timezone(timedelta(hours=9))
    today = datetime.now(tz=kst)
    bgn_de = (today - timedelta(days=7)).strftime("%Y%m%d")
    end_de = today.strftime("%Y%m%d")

    async for db in get_db():
        try:
            svc = BronzeEconomicIngestService(db, settings.dart_api_key)
            print(f"[1/2] 수집 중 ({bgn_de}~{end_de}, max_pages=10)...")
            result = await svc.ingest_nps_portfolio(bgn_de=bgn_de, end_de=end_de, max_pages=10)

            print("\n수집 결과:")
            print(f"  - watermark    : {result['watermark']}")
            print(f"  - fetched      : {result['fetched']}")
            print(f"  - inserted     : {result['inserted']}")
            print(f"  - not_inserted : {result['not_inserted']}")
            print(f"  - stats        : {result['stats']}")

            if result["inserted"] > 0:
                from sqlalchemy import select
                from domain.master.models.bases.raw_economic_data import RawEconomicData

                stmt = (
                    select(RawEconomicData)
                    .where(RawEconomicData.source_type == "NPS_PORTFOLIO_DART")
                    .order_by(RawEconomicData.published_at.desc().nullslast())
                    .limit(5)
                )
                rows = (await db.execute(stmt)).scalars().all()
                print(f"\n[2/2] 샘플 {len(rows)}건:")
                for i, row in enumerate(rows, 1):
                    meta = row.raw_metadata or {}
                    print(f"  [{i}] {row.raw_title[:50]} | {meta.get('rcept_dt','')}")

            print("\n[SUCCESS] NPS 테스트 완료!")
            break
        except Exception as e:
            print(f"\n[ERROR] NPS 테스트 실패: {e}")
            import traceback
            traceback.print_exc()
            break


async def main() -> None:
    await test_nps_portfolio()


if __name__ == "__main__":
    asyncio.run(main())
