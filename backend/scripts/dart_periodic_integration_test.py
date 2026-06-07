"""DART 정기공시(A) 수집 통합 테스트 (라이브 + DB).

실행: python scripts/dart_periodic_integration_test.py
요구: .env 의 DART_API_KEY, DATABASE_URL.
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


async def test_dart_periodic() -> None:
    print("\n" + "=" * 80)
    print("DART 정기공시(A) 수집 통합 테스트 시작")
    print("=" * 80 + "\n")

    settings = get_settings()
    if not settings.dart_api_key:
        print("[SKIP] DART_API_KEY 미설정 — .env 에 키를 넣고 다시 실행하세요.")
        return

    kst = timezone(timedelta(hours=9))
    now = datetime.now(tz=kst)
    # 최근 35일 범위
    bgn_de = (now - timedelta(days=35)).strftime("%Y%m%d")
    end_de = now.strftime("%Y%m%d")

    async for db in get_db():
        try:
            svc = BronzeEconomicIngestService(db, settings.dart_api_key)
            print(f"[1/2] 정기공시(A) 수집 중 ({bgn_de}~{end_de}, enrich_financials=True, max_enrich=50)...")
            result = await svc.ingest_dart_periodic(
                bgn_de=bgn_de,
                end_de=end_de,
                enrich_financials=True,
                max_enrich=50,
            )

            print("\n수집 결과:")
            print(f"  - source            : {result['source']}")
            print(f"  - fetched           : {result['fetched']}")
            print(f"  - inserted          : {result['inserted']}")
            print(f"  - not_inserted      : {result['not_inserted']}")
            print(f"  - source_type_counts: {result['source_type_counts']}")
            print(f"  - stats             : {result['stats']}")

            if result["fetched"] > 0:
                print("\n[2/2] 샘플 데이터 조회 중...")
                from sqlalchemy import select

                from domain.master.models.bases.raw_economic_data import RawEconomicData

                stmt = (
                    select(RawEconomicData)
                    .where(
                        RawEconomicData.source_type.in_(
                            ["DART_PERIODIC_ANNUAL", "DART_PERIODIC_SEMIANNUAL"]
                        )
                    )
                    .order_by(RawEconomicData.published_at.desc().nullslast())
                    .limit(5)
                )
                rows = (await db.execute(stmt)).scalars().all()
                for i, row in enumerate(rows, 1):
                    meta = row.raw_metadata or {}
                    print(f"\n--- 샘플 {i} ---")
                    print(f"기업/보고서: {row.raw_title}")
                    print(f"source_type: {row.source_type}")
                    print(f"접수일     : {row.published_at}")
                    rnd = meta.get("rnd_amount")
                    capex = meta.get("capex_amount")
                    print(f"R&D        : {rnd:,}원" if rnd else "R&D        : (없음)")
                    print(f"CAPEX      : {capex:,}원" if capex else "CAPEX      : (없음)")
                    print(f"URL        : {row.source_url}")

            print("\n[SUCCESS] 테스트 완료!")
            break
        except Exception as e:
            print(f"\n[ERROR] 테스트 실패: {e}")
            import traceback
            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(test_dart_periodic())
