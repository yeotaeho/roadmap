"""보조금24 수집 통합 테스트 (라이브 + DB).

실행: python scripts/subsidy24_integration_test.py
요구: .env 의 SUBSIDY24_SERVICE_KEY, DATABASE_URL.
"""

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.config.settings import get_settings  # noqa: E402
from core.database import get_db  # noqa: E402
from domain.master.hub.services.bronze_economic_ingest_service import (  # noqa: E402
    BronzeEconomicIngestService,
)


async def test_subsidy24() -> None:
    print("\n" + "=" * 80)
    print("보조금24 수집 통합 테스트 시작")
    print("=" * 80 + "\n")

    settings = get_settings()
    if not settings.subsidy24_service_key:
        print("[SKIP] SUBSIDY24_SERVICE_KEY 미설정 — .env 에 키를 넣고 다시 실행하세요.")
        print("       발급: https://www.data.go.kr/data/15113968/openapi.do")
        return

    async for db in get_db():
        try:
            svc = BronzeEconomicIngestService(
                db, None, subsidy24_service_key=settings.subsidy24_service_key
            )
            print("[1/2] 보조금24 서비스 목록 수집 중 (max_items=50, 증분 테스트)...")
            result = await svc.ingest_subsidy24(max_items=50)

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
                    .where(RawEconomicData.source_type == "GOVT_SUBSIDY24")
                    .order_by(RawEconomicData.published_at.desc().nullslast())
                    .limit(5)
                )
                rows = (await db.execute(stmt)).scalars().all()
                for i, row in enumerate(rows, 1):
                    meta = row.raw_metadata or {}
                    print(f"\n--- 샘플 {i} ---")
                    print(f"서비스명  : {row.raw_title}")
                    print(f"소관기관  : {meta.get('institution')}")
                    print(f"분야/유형 : {meta.get('service_category')} / {meta.get('support_type')}")
                    print(f"지원금액  : {row.investment_amount} 원" if row.investment_amount else "지원금액  : (파싱 불가)")
                    print(f"수정일시  : {meta.get('modified_at_raw')}")
                    print(f"URL       : {row.source_url}")

            print("\n[SUCCESS] 테스트 완료!")
            break
        except Exception as e:
            print(f"\n[ERROR] 테스트 실패: {e}")
            import traceback
            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(test_subsidy24())
