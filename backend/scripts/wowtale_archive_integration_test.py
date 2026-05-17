"""Wowtale 아카이브 크롤러 통합 테스트.

실제 HTTP 요청 + DB 적재까지 검증한다 (소규모: 1~2페이지).

사용법::

    cd backend
    python scripts/wowtale_archive_integration_test.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import get_db
from domain.master.hub.services.bronze_economic_ingest_service import (
    BronzeEconomicIngestService,
)
from domain.master.hub.services.collectors.economic.wowtale_archive_crawler import (
    WowtaleArchiveCrawler,
    _fetch_html,
    _parse_archive_page,
    _parse_article_page,
)

_KST = timezone(timedelta(hours=9))


async def test_archive_crawler() -> None:
    print("\n" + "=" * 70)
    print("Wowtale 아카이브 크롤러 통합 테스트")
    print("=" * 70)

    # ------------------------------------------------------------------
    # [1] 카테고리 아카이브 페이지 파싱 테스트
    # ------------------------------------------------------------------
    print("\n[1/4] 카테고리 아카이브 페이지 파싱 테스트 (funding p.1)")
    html = _fetch_html("https://wowtale.net/category/funding/")
    if not html:
        print("  FAIL: HTML 응답 없음")
        return

    refs, has_next = _parse_archive_page(html, "funding")
    print(f"  기사 수     : {len(refs)}건")
    print(f"  다음 페이지  : {has_next}")
    if refs:
        sample = refs[0]
        print(f"  샘플 제목   : {sample.title[:60]}...")
        print(f"  샘플 URL    : {sample.url}")
        print(f"  URL 날짜    : {sample.published_at}")

    assert refs, "기사 목록이 비어 있습니다 — 셀렉터 확인 필요"
    assert has_next, "다음 페이지가 없습니다 — 페이지네이션 셀렉터 확인 필요"
    print("  OK")

    # ------------------------------------------------------------------
    # [2] 기사 상세 페이지 파싱 테스트
    # ------------------------------------------------------------------
    print("\n[2/4] 기사 상세 페이지 파싱 테스트")
    if refs:
        article_html = _fetch_html(refs[0].url)
        published_at, body_text = _parse_article_page(article_html)
        print(f"  발행일     : {published_at}")
        print(f"  본문 길이  : {len(body_text)}자")
        if body_text:
            print(f"  본문 미리보기: {body_text[:100]}...")
        assert body_text, "본문이 비어 있습니다 — entry-content 셀렉터 확인 필요"
    print("  OK")

    # ------------------------------------------------------------------
    # [3] 크롤러 소규모 실행 테스트 (1페이지, DB 적재 전)
    # ------------------------------------------------------------------
    print("\n[3/4] 크롤러 소규모 실행 (funding 1페이지, DB 적재 안 함)")
    crawler = WowtaleArchiveCrawler(sleep_sec=0.5, article_sleep_sec=0.3)
    dtos = await crawler.crawl_category("funding", max_pages=1)
    print(f"  수집 건수   : {len(dtos)}건")
    if dtos:
        sample_dto = dtos[0]
        print(f"  샘플 제목   : {sample_dto.raw_title[:60]}...")
        print(f"  source_type : {sample_dto.source_type}")
        print(f"  투자 금액   : {sample_dto.investment_amount:,}원" if sample_dto.investment_amount else "  투자 금액   : 없음")
        print(f"  투자자      : {sample_dto.investor_name}")
        print(f"  발행일      : {sample_dto.published_at}")
    assert dtos, "DTO 목록이 비어 있습니다"
    print("  OK")

    # ------------------------------------------------------------------
    # [4] DB 적재 통합 테스트 (소규모: 1페이지, from_date=오늘-7일)
    # ------------------------------------------------------------------
    print("\n[4/4] DB 적재 통합 테스트 (funding 1페이지, 최근 7일)")
    from_date = datetime.now(_KST) - timedelta(days=7)

    async for db in get_db():
        try:
            svc = BronzeEconomicIngestService(db, None)
            result = await svc.ingest_wowtale_archive(
                max_pages=1,
                from_date=from_date,
                fetch_article_body=True,
                categories=[("funding", False)],
            )
            print(f"  수집 건수   : {result['fetched']:,}건")
            print(f"  신규 삽입   : {result['inserted']:,}건")
            print(f"  중복 스킵   : {result['not_inserted']:,}건")
            print(f"  source_type : {result['source_type_counts']}")
            print("  OK")
            break
        except Exception as e:
            print(f"  FAIL: {e}")
            import traceback
            traceback.print_exc()
            break

    print("\n" + "=" * 70)
    print("모든 테스트 완료")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(test_archive_crawler())
