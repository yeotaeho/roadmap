"""MFDS 보도자료 수집 통합 테스트 (라이브 + DB).

실행: python scripts/mfds_integration_test.py
요구: DATABASE_URL 연결, mfds.go.kr 아웃바운드 네트워크. 키 불필요.
"""

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.database import get_db  # noqa: E402
from domain.master.hub.services.bronze_economic_ingest_service import (  # noqa: E402
    BronzeEconomicIngestService,
)


async def test_mfds_collection() -> None:
    print("\n" + "=" * 80)
    print("MFDS 보도자료 수집 통합 테스트 시작")
    print("=" * 80 + "\n")

    async for db in get_db():
        try:
            svc = BronzeEconomicIngestService(db, None)

            print("[1/2] MFDS 보도자료 수집 중 (max_pages=3, year 필터 기본)...")
            result = await svc.ingest_mfds_press(max_pages=3, max_items=30, fetch_body=True)

            print("\n수집 결과:")
            print(f"  - source       : {result['source']}")
            print(f"  - source_type  : {result['source_type']}")
            print(f"  - target_year  : {result['target_year']}")
            print(f"  - fetched      : {result['fetched']}")
            print(f"  - inserted     : {result['inserted']}")
            print(f"  - not_inserted : {result['not_inserted']}")
            print(f"  - stats        : {result['stats']}")
            print(f"  - watermark    : {result['watermark']}")

            if result["fetched"] > 0:
                print("\n[2/2] 샘플 데이터 조회 중...")
                from sqlalchemy import select

                from domain.master.models.bases.raw_economic_data import RawEconomicData

                stmt = (
                    select(RawEconomicData)
                    .where(RawEconomicData.source_type == "GOVT_MFDS_APPROVAL")
                    .order_by(RawEconomicData.published_at.desc().nullslast())
                    .limit(5)
                )
                rows = (await db.execute(stmt)).scalars().all()
                for i, row in enumerate(rows, 1):
                    print(f"\n--- 샘플 {i} ---")
                    print(f"제목     : {row.raw_title}")
                    print(f"발행일   : {row.published_at}")
                    print(f"URL      : {row.source_url}")
                    meta = row.raw_metadata or {}
                    print(f"섹터/신호: {meta.get('industry_sector')} / {meta.get('signal_priority')}")
                    print(f"본문길이 : {meta.get('body_text_length')}")

            print("\n[SUCCESS] 테스트 완료!")
            break
        except Exception as e:
            print(f"\n[ERROR] 테스트 실패: {e}")
            import traceback

            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(test_mfds_collection())
