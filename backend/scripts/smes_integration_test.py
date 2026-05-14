"""중소벤처기업부 사업공고 OpenAPI 수집 통합 테스트."""

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.config.settings import get_settings
from core.database import get_db
from domain.master.hub.services.bronze_opportunity_ingest_service import (
    BronzeOpportunityIngestService,
)


async def test_smes_collection() -> None:
    print("\n" + "=" * 80)
    print("중소벤처기업부 사업공고 OpenAPI 수집 통합 테스트")
    print("=" * 80 + "\n")

    settings = get_settings()
    if not settings.smes_service_key:
        print("[ERROR] SMES_SERVICE_KEY 가 .env 에 설정되어 있지 않습니다.")
        print("        공공데이터포털 승인 후 발급받은 키를 .env 에 넣어주세요.")
        return

    async for db in get_db():
        try:
            svc = BronzeOpportunityIngestService(db, settings.smes_service_key)

            print("[1/2] 중소벤처 OpenAPI 호출 중...")
            result = await svc.ingest_smes(max_items=20)

            print("\n" + "=" * 80)
            print("수집 결과:")
            print(f"  - 출처:         {result['source']}")
            print(f"  - 가져온 건수:  {result['fetched']}")
            print(f"  - 신규 삽입:    {result['inserted']}")
            print(f"  - 중복 스킵:    {result['not_inserted']}")
            print("=" * 80)

            if result["fetched"] > 0:
                print("\n[2/2] 샘플 데이터 조회 중...")
                from sqlalchemy import func, select

                from domain.master.models.bases.raw_opportunity_data import (
                    RawOpportunityData,
                )

                stmt = (
                    select(RawOpportunityData)
                    .where(RawOpportunityData.source_type.like("SMES_%"))
                    .order_by(RawOpportunityData.collected_at.desc())
                    .limit(5)
                )
                rows = (await db.execute(stmt)).scalars().all()

                for i, row in enumerate(rows, 1):
                    print(f"\n--- 샘플 {i} ---")
                    print(f"source_type: {row.source_type}")
                    print(f"제목:       {row.raw_title}")
                    print(f"주관기관:    {row.host_name}")
                    print(f"URL:        {row.source_url[:80]}")
                    print(f"게시일:      {row.published_at}")
                    print(f"마감일:      {row.deadline_at}")
                    if row.raw_metadata:
                        keys = list(row.raw_metadata.keys())
                        print(f"메타키:      {keys}")
                        if "application_period" in row.raw_metadata:
                            print(
                                f"접수기간:    {row.raw_metadata['application_period']}"
                            )
                        if "budget" in row.raw_metadata:
                            print(f"예산:        {row.raw_metadata['budget']}")
                    if row.raw_content:
                        preview = row.raw_content[:150].replace("\n", " ")
                        print(f"본문 미리:   {preview}...")

                print("\n" + "=" * 80)
                print("[STATS] SMES source_type 분포:")
                stmt_count = (
                    select(
                        RawOpportunityData.source_type,
                        func.count(RawOpportunityData.id).label("cnt"),
                    )
                    .where(RawOpportunityData.source_type.like("SMES_%"))
                    .group_by(RawOpportunityData.source_type)
                )
                for stype, cnt in (await db.execute(stmt_count)).all():
                    print(f"  - {stype}: {cnt}건")

            print("\n[SUCCESS] 테스트 완료!")
            break

        except Exception as e:
            print(f"\n[ERROR] 테스트 실패: {e}")
            import traceback

            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(test_smes_collection())
