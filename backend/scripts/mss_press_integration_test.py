"""중소벤처기업부(MSS) 보도자료 수집 통합 테스트 (라이브 + DB).

실행: python scripts/mss_press_integration_test.py
요구: .env 의 DATABASE_URL (API 키 불필요).
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


async def test_mss_press() -> None:
    print("\n" + "=" * 80)
    print("중소벤처기업부(MSS) 보도자료 수집 통합 테스트 시작")
    print("=" * 80 + "\n")

    async for db in get_db():
        try:
            svc = BronzeEconomicIngestService(db, None)
            print("[1/2] MSS 보도자료 수집 중 (max_items=30, 증분 테스트)...")
            result = await svc.ingest_mss_press(max_items=30)

            print("\n수집 결과:")
            print(f"  - source       : {result['source']}")
            print(f"  - watermark    : {result['watermark']}")
            print(f"  - fetched      : {result['fetched']}")
            print(f"  - inserted     : {result['inserted']}")
            print(f"  - not_inserted : {result['not_inserted']}")
            print(f"  - stats        : {result['stats']}")

            if result["fetched"] > 0:
                print("\n[2/2] 샘플 데이터 조회 중...")
                from sqlalchemy import select

                from domain.master.models.bases.raw_economic_data import RawEconomicData

                stmt = (
                    select(RawEconomicData)
                    .where(RawEconomicData.source_type == "GOVT_MSS_PRESS")
                    .order_by(RawEconomicData.published_at.desc().nullslast())
                    .limit(5)
                )
                rows = (await db.execute(stmt)).scalars().all()
                for i, row in enumerate(rows, 1):
                    meta = row.raw_metadata or {}
                    print(f"\n--- 샘플 {i} ---")
                    print(f"제목      : {row.raw_title}")
                    print(f"담당부서  : {meta.get('dept')}")
                    print(f"등록일    : {row.published_at}")
                    print(f"지원금액  : {row.investment_amount:,}원" if row.investment_amount else "지원금액  : (파싱 불가)")
                    print(f"bcIdx    : {meta.get('bc_idx')}")
                    print(f"URL       : {row.source_url}")

            print("\n[SUCCESS] 테스트 완료!")
            break
        except Exception as e:
            print(f"\n[ERROR] 테스트 실패: {e}")
            import traceback
            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(test_mss_press())
