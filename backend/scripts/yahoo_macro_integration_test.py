"""Yahoo Macro 가격 변동(Price Surge) Z-score 수집 통합 테스트.

대상 (총 8종):
  - FX 3종       (USDKRW / EURKRW / JPYKRW)
  - 미 국채금리 2종 (^TNX / ^IRX)
  - 원자재 2종    (금 / WTI 원유)
  - 가상자산 1종  (BTC-USD)
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


async def test_yahoo_macro_collection():
    print("\n" + "=" * 80)
    print("Yahoo Macro Z-score Price Surge 통합 테스트 시작")
    print("  대상: FX 3 + 금리 2 + 원자재 2 + 가상자산 1 = 총 8종")
    print("  알고리즘: |일간 수익률| / 20일 σ ≥ Z 임계값 (2.0~2.5)")
    print("=" * 80 + "\n")

    async for db in get_db():
        try:
            svc = BronzeEconomicIngestService(db, None)

            print("[1/2] Yahoo Macro 데이터 수집 중...")
            print("       (티커 간 0.5s sleep — 약 4초 소요)\n")

            result = await svc.ingest_yahoo_macro()

            print("=" * 80)
            print("수집 결과:")
            print(f"  - 출처              : {result['source']}")
            print(f"  - 감지된 Z-score 신호: {result['fetched']}건")
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
                        RawEconomicData.source_type.like("YAHOO_FX_%")
                        | RawEconomicData.source_type.like("YAHOO_RATE_%")
                        | RawEconomicData.source_type.like("YAHOO_COMMODITY_%")
                    )
                    .order_by(RawEconomicData.collected_at.desc())
                    .limit(20)
                )
                rows = (await db.execute(stmt)).scalars().all()

                for i, row in enumerate(rows, 1):
                    print(f"\n--- 샘플 {i} ---")
                    print(f"source_type   : {row.source_type}")
                    print(f"제목          : {row.raw_title}")
                    print(f"대상 자산      : {row.target_company_or_fund}")
                    print(f"통화/단위      : {row.currency}")
                    print(f"거래일         : {row.published_at}")
                    if row.raw_metadata:
                        meta = row.raw_metadata
                        print(f"카테고리       : {meta.get('category')}")
                        print(f"단위           : {meta.get('unit')}")
                        print(f"종가/전일종가  : {meta.get('close')} / {meta.get('prev_close')}")
                        print(
                            f"일간 수익률    : {meta.get('daily_return_pct')}%  "
                            f"방향: {meta.get('direction')}"
                        )
                        print(
                            f"Z-score        : {meta.get('z_score')} "
                            f"(임계값 {meta.get('threshold')}, σ_20={meta.get('std_20d')})"
                        )

            print("\n" + "=" * 80)
            print("[STATS] 카테고리별 source_type 분포 (전체 누적):")
            print("=" * 80)
            for prefix, label in [
                ("YAHOO_FX_%", "환율(FX) — 외국인 자본 이동"),
                ("YAHOO_RATE_%", "금리(RATE) — 글로벌 자본 비용"),
                ("YAHOO_COMMODITY_%", "원자재/가상자산(COMMODITY)"),
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
                    print("    (적재된 데이터 없음 — 오늘은 안정기)")
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
    asyncio.run(test_yahoo_macro_collection())
