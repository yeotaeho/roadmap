"""raw_economic_data 스키마 검증 스크립트."""

import asyncio
import sys
from pathlib import Path

# PYTHONPATH 설정
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.database import get_db
from domain.master.models.bases.raw_economic_data import RawEconomicData
from sqlalchemy import select


async def verify_data():
    """샘플 데이터 조회 및 스키마 검증."""
    async for db in get_db():
        try:
            # 최근 5건 조회
            stmt = (
                select(RawEconomicData)
                .order_by(RawEconomicData.collected_at.desc())
                .limit(5)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                print("[ERROR] 데이터가 없습니다.")
                return

            print(f"\n[SUCCESS] 총 {len(rows)}건 조회됨\n")

            for i, row in enumerate(rows, 1):
                print(f"{'=' * 80}")
                print(f"[{i}] ID: {row.id}")
                print(f"source_type: {row.source_type}")
                print(f"source_url: {row.source_url[:80]}..." if row.source_url and len(row.source_url) > 80 else f"source_url: {row.source_url}")
                print(f"raw_title: {row.raw_title}")
                print(f"investor_name: {row.investor_name}")
                print(f"target_company_or_fund: {row.target_company_or_fund}")
                print(f"investment_amount: {row.investment_amount}")
                print(f"currency: {row.currency}")
                print(f"raw_metadata: {row.raw_metadata}")
                print(f"published_at: {row.published_at}")
                print(f"collected_at: {row.collected_at}")

            # source_type 별 통계
            print(f"\n{'=' * 80}")
            print("[STATS] source_type 별 통계:")
            from sqlalchemy import func

            stmt_count = select(
                RawEconomicData.source_type,
                func.count(RawEconomicData.id).label("count"),
            ).group_by(RawEconomicData.source_type)
            result_count = await db.execute(stmt_count)
            stats = result_count.all()

            for source_type, count in stats:
                print(f"  - {source_type}: {count}건")

            print(f"\n[SUCCESS] 스키마 검증 완료!")
            break
        except Exception as e:
            print(f"[ERROR] 에러 발생: {e}")
            import traceback

            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(verify_data())
