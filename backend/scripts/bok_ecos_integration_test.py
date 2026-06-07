"""한국은행 ECOS 수집 통합 테스트 (라이브 + DB).

실행: python scripts/bok_ecos_integration_test.py
요구: .env 의 BOK_ECOS_API_KEY, DATABASE_URL 연결, ecos.bok.or.kr 아웃바운드 네트워크.

NOTE: 통계표/항목 코드는 컬렉터 `_ECOS_TARGETS` 에 정의(현재 기준금리만 활성).
      M2·FDI 등은 StatisticTableList Probe 로 코드 확정 후 주석 해제.
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


async def test_bok_ecos_collection() -> None:
    print("\n" + "=" * 80)
    print("BOK ECOS 거시 시계열 수집 통합 테스트 시작")
    print("=" * 80 + "\n")

    settings = get_settings()
    if not settings.bok_ecos_api_key:
        print("[SKIP] BOK_ECOS_API_KEY 미설정 — .env 에 키를 넣고 다시 실행하세요.")
        print("       발급: https://ecos.bok.or.kr/api/#/AuthKeyApply")
        return

    kst = timezone(timedelta(hours=9))
    now = datetime.now(tz=kst)
    start = (now - timedelta(days=400)).strftime("%Y%m")
    end = now.strftime("%Y%m")

    async for db in get_db():
        try:
            svc = BronzeEconomicIngestService(
                db, None, bok_ecos_api_key=settings.bok_ecos_api_key
            )
            print(f"[1/2] ECOS 월간 시계열 수집 중 ({start}~{end})...")
            result = await svc.ingest_bok_ecos(start=start, end=end)

            print("\n수집 결과:")
            print(f"  - source            : {result['source']}")
            print(f"  - fetched           : {result['fetched']}")
            print(f"  - inserted          : {result['inserted']}")
            print(f"  - not_inserted      : {result['not_inserted']}")
            print(f"  - source_type_counts: {result['source_type_counts']}")
            print(f"  - range             : {result['range']}")

            if result["fetched"] > 0:
                print("\n[2/2] 샘플 데이터 조회 중...")
                from sqlalchemy import select

                from domain.master.models.bases.raw_economic_data import RawEconomicData

                stmt = (
                    select(RawEconomicData)
                    .where(RawEconomicData.source_type.like("BOK_ECOS_%"))
                    .order_by(RawEconomicData.published_at.desc().nullslast())
                    .limit(5)
                )
                rows = (await db.execute(stmt)).scalars().all()
                for i, row in enumerate(rows, 1):
                    meta = row.raw_metadata or {}
                    print(f"\n--- 샘플 {i} ---")
                    print(f"제목   : {row.raw_title}")
                    print(f"값/단위: {meta.get('data_value')} {meta.get('unit_name')}")
                    print(f"amount : {row.investment_amount} (flow={meta.get('is_flow')})")
                    print(f"URL키  : {row.source_url}")

            print("\n[SUCCESS] 테스트 완료!")
            break
        except Exception as e:
            print(f"\n[ERROR] 테스트 실패: {e}")
            import traceback

            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(test_bok_ecos_collection())
