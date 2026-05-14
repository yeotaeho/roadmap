"""Wowtale RSS 수집 통합 테스트."""

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.database import get_db
from domain.master.hub.services.bronze_economic_ingest_service import BronzeEconomicIngestService


async def test_wowtale_collection():
    """Wowtale RSS 피드 수집 테스트."""
    print("\n" + "=" * 80)
    print("Wowtale RSS 수집 통합 테스트 시작")
    print("=" * 80 + "\n")

    async for db in get_db():
        try:
            svc = BronzeEconomicIngestService(db, None)

            print("[1/2] Wowtale RSS 피드 수집 중...")
            result = await svc.ingest_wowtale(max_items=10)

            print("\n" + "=" * 80)
            print("수집 결과:")
            print(f"  - 출처: {result['source']}")
            print(f"  - 가져온 건수: {result['fetched']}")
            print(f"  - 신규 삽입: {result['inserted']}")
            print(f"  - 중복 스킵: {result['not_inserted']}")
            print(f"  - 노이즈 필터 스킵: {result.get('skipped_noise', 0)}")
            print("=" * 80)

            if result["fetched"] > 0:
                print("\n[2/2] 샘플 데이터 조회 중...")
                from sqlalchemy import func, select
                from domain.master.models.bases.raw_economic_data import RawEconomicData

                stmt = (
                    select(RawEconomicData)
                    .where(RawEconomicData.source_type.like("WOWTALE_%"))
                    .order_by(RawEconomicData.collected_at.desc())
                    .limit(5)
                )
                rows = (await db.execute(stmt)).scalars().all()

                for i, row in enumerate(rows, 1):
                    print(f"\n--- 샘플 {i} ---")
                    print(f"source_type: {row.source_type}")
                    print(f"제목: {row.raw_title}")
                    print(f"투자사: {row.investor_name}")
                    print(f"URL: {row.source_url[:80]}...")
                    print(f"발행일: {row.published_at}")
                    if row.raw_metadata:
                        keys = list(row.raw_metadata.keys())
                        print(f"메타데이터 키: {keys}")
                        if "content_source" in row.raw_metadata:
                            print(f"본문 출처: {row.raw_metadata['content_source']}")
                        if "content_text" in row.raw_metadata:
                            preview = row.raw_metadata["content_text"][:120]
                            print(f"본문 미리보기: {preview}...")

                print("\n" + "=" * 80)
                print("[STATS] WOWTALE source_type 분포:")
                stmt_count = (
                    select(
                        RawEconomicData.source_type,
                        func.count(RawEconomicData.id).label("cnt"),
                    )
                    .where(RawEconomicData.source_type.like("WOWTALE_%"))
                    .group_by(RawEconomicData.source_type)
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
    asyncio.run(test_wowtale_collection())
