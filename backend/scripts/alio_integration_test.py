"""ALIO 공공기관 사업정보 Collector 단위·연동 점검 스크립트.

실행 (backend 디렉터리, API 키·네트워크 필요):

  python scripts/alio_integration_test.py

`.env` 의 `ALIO_SERVICE_KEY` 를 사용합니다.
"""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path

_BACKEND_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from core.config.settings import get_settings
from domain.master.hub.services.collectors.economic.alio_public_inst_project_collector import (
    AlioPublicInstProjectCollector,
)


async def _run() -> None:
    print("\n" + "=" * 72)
    print("ALIO 공공기관 사업정보 Collector 통합 점검 (Economic / raw_economic_data)")
    print("=" * 72 + "\n")

    settings = get_settings()
    key = (settings.alio_service_key or "").strip()
    if not key:
        print("[오류] ALIO_SERVICE_KEY 가 .env 에 없습니다.")
        return

    collector = AlioPublicInstProjectCollector(key)

    print("[테스트 1] 필터 완화(기관 전체·키워드 미적용)로 최대 10건 수집")
    batch1 = await collector.collect(
        max_items=10,
        inst_filter=[],
        disable_keyword_filter=True,
    )
    print(f"  → 건수: {len(batch1)}")
    for dto in batch1[:5]:
        print(f"     - [{dto.source_type}] {dto.raw_title[:80]} | inv={dto.investor_name!s}")

    print("\n[테스트 2] inst_filter=['한국산업기술진흥원'], 최대 10건")
    batch2 = await collector.collect(
        max_items=10,
        inst_filter=["한국산업기술진흥원"],
    )
    print(f"  → 건수: {len(batch2)}")
    for dto in batch2[:5]:
        print(f"     - [{dto.source_type}] {dto.raw_title[:80]} | amt={dto.investment_amount}")

    print("\n[테스트 3] biz_year=2026, 최대 10건")
    batch3 = await collector.collect(max_items=10, biz_year=2026, inst_filter=[])
    print(f"  → 건수: {len(batch3)}")
    for dto in batch3[:5]:
        print(f"     - [{dto.source_type}] {dto.raw_title[:80]}")

    merged = batch1 + batch2 + batch3
    dist = Counter(d.source_type for d in merged)
    print("\n" + "=" * 72)
    print("[요약] 세 배치 합산 source_type 분포 (중복 URL 가능)")
    for st, n in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {st}: {n}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    asyncio.run(_run())
