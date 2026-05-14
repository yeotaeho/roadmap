"""Yahoo Finance 거래량 급증(Volume Surge) 수집 통합 테스트.

검증 대상 (Option B 확장 — 총 16종):
  - 한국 테마 ETF 5종     (`YAHOO_ETF_*`)
  - 한국 대형주 5종       (`YAHOO_STOCK_KR_*`)
  - 글로벌 ETF 6종        (`YAHOO_GLOBAL_*`)
"""

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.database import get_db
from domain.master.hub.services.bronze_economic_ingest_service import (
    BronzeEconomicIngestService,
)


async def test_yahoo_finance_collection():
    print("\n" + "=" * 80)
    print("Yahoo Finance Volume Surge 통합 테스트 시작")
    print("  대상: 한국 ETF 5 + 한국 대형주 5 + 글로벌 ETF 6 = 총 16종")
    print("=" * 80 + "\n")

    async for db in get_db():
        try:
            svc = BronzeEconomicIngestService(db, None)

            print("[1/2] Yahoo Finance Volume Surge 데이터 수집 중...")
            print("       (티커 간 0.5s sleep 으로 IP 차단 방어 — 약 8초 소요)\n")

            result = await svc.ingest_yahoo_finance()

            print("=" * 80)
            print("수집 결과:")
            print(f"  - 출처              : {result['source']}")
            print(f"  - 감지된 급증 신호  : {result['fetched']}건")
            print(f"  - 신규 삽입         : {result['inserted']}건")
            print(f"  - 중복 스킵         : {result['not_inserted']}건")
            print(f"  - 미감지(임계값 미달): {result['skipped_no_signal']}건")
            print("=" * 80)

            from sqlalchemy import func, select

            from domain.master.models.bases.raw_economic_data import RawEconomicData

            if result["fetched"] > 0:
                print("\n[2/2] 샘플 데이터 조회 중...")
                stmt = (
                    select(RawEconomicData)
                    .where(
                        RawEconomicData.source_type.like("YAHOO_ETF_%")
                        | RawEconomicData.source_type.like("YAHOO_STOCK_KR_%")
                        | RawEconomicData.source_type.like("YAHOO_GLOBAL_%")
                    )
                    .order_by(RawEconomicData.collected_at.desc())
                    .limit(20)
                )
                rows = (await db.execute(stmt)).scalars().all()

                for i, row in enumerate(rows, 1):
                    print(f"\n--- 샘플 {i} ---")
                    print(f"source_type        : {row.source_type}")
                    print(f"제목               : {row.raw_title}")
                    print(f"대상 자산          : {row.target_company_or_fund}")
                    print(f"통화               : {row.currency}")
                    if row.investment_amount is not None:
                        print(f"추정 유입액        : {row.investment_amount:,}")
                    print(f"거래일(KST)        : {row.published_at}")
                    if row.raw_metadata:
                        meta = row.raw_metadata
                        print(f"티커               : {meta.get('ticker')}")
                        print(f"테마               : {meta.get('theme')}")
                        print(
                            f"거래량 비율        : {meta.get('volume_ratio')}배 "
                            f"(임계값 {meta.get('threshold')}배)"
                        )

            print("\n" + "=" * 80)
            print("[STATS] 그룹별 source_type 분포 (전체 누적):")
            print("=" * 80)
            for prefix, label in [
                ("YAHOO_ETF_%", "한국 테마 ETF"),
                ("YAHOO_STOCK_KR_%", "한국 대형주"),
                ("YAHOO_GLOBAL_%", "글로벌 ETF (선행 지표)"),
            ]:
                stmt_count = (
                    select(
                        RawEconomicData.source_type,
                        func.count(RawEconomicData.id).label("cnt"),
                    )
                    .where(RawEconomicData.source_type.like(prefix))
                    .group_by(RawEconomicData.source_type)
                )
                rows_c = (await db.execute(stmt_count)).all()
                print(f"\n  [{label}]")
                if not rows_c:
                    print("    (적재된 데이터 없음 — 임계값 미달이거나 오늘은 안정기)")
                for stype, cnt in rows_c:
                    print(f"    - {stype}: {cnt}건")

            print("\n[SUCCESS] 테스트 완료!")
            break

        except Exception as e:
            print(f"\n[ERROR] 테스트 실패: {e}")
            import traceback

            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(test_yahoo_finance_collection())
