"""Wowtale 아카이브 과거 데이터 Backfill CLI.

카테고리 아카이브 페이지(/category/funding/page/N/ 등)를 순회해
RSS 수집기가 커버하지 못하는 과거 기사를 raw_economic_data 에 적재한다.

사용법::

    cd backend

    # 기본 실행 (최근 1년, funding + venture-capital + Global-news)
    python scripts/wowtale_backfill.py

    # 날짜 컷오프 지정
    python scripts/wowtale_backfill.py --from-date 2025-01-01

    # 특정 카테고리만, 본문 크롤링 스킵 (빠름)
    python scripts/wowtale_backfill.py --categories funding --no-article-body

    # 페이지 수 제한 (테스트용)
    python scripts/wowtale_backfill.py --max-pages 3 --categories funding

예상 소요 시간 (기본 설정):
    본문 크롤링 ON  : 3 카테고리 × 50 페이지 × 20건 × 1.5초 ≈ 75분
    본문 크롤링 OFF : 3 카테고리 × 50 페이지 × 1초 ≈ 2.5분
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# backend 패키지를 Python path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import AsyncSessionLocal
from domain.master.hub.services.bronze_economic_ingest_service import (
    BronzeEconomicIngestService,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("wowtale_backfill")

_KST = timezone(timedelta(hours=9))

# 투자 노이즈 필터를 적용해야 하는 카테고리 (복합 카테고리)
_FILTER_SLUGS = frozenset({"Global-news", "ai", "bio-healthcare"})


def _build_categories(slugs: list[str]) -> list[tuple[str, bool]]:
    return [(slug, slug in _FILTER_SLUGS) for slug in slugs]


async def run_backfill(
    *,
    max_pages: int,
    from_date: datetime | None,
    category_slugs: list[str] | None,
    fetch_article_body: bool,
    sleep_sec: float,
) -> dict:
    categories = _build_categories(category_slugs) if category_slugs else None

    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None)
        result = await svc.ingest_wowtale_archive(
            max_pages=max_pages,
            from_date=from_date,
            fetch_article_body=fetch_article_body,
            sleep_sec=sleep_sec,
            categories=categories,
        )

    return result


def _print_result(result: dict) -> None:
    print("\n" + "=" * 60)
    print("  Wowtale Archive Backfill 결과")
    print("=" * 60)
    print(f"  수집 건수   : {result.get('fetched', 0):,}건")
    print(f"  신규 삽입   : {result.get('inserted', 0):,}건")
    print(f"  중복 스킵   : {result.get('not_inserted', 0):,}건")
    type_counts = result.get("source_type_counts", {})
    if type_counts:
        print("\n  source_type 분포:")
        for stype, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"    {stype:<30} {cnt:>5}건")
    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wowtale 카테고리 아카이브 Backfill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--from-date",
        default=None,
        metavar="YYYY-MM-DD",
        help="이 날짜 이전 기사 수집 중단 (기본: 1년 전)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        metavar="N",
        help="카테고리당 최대 페이지 수 (기본: 50, 페이지당 ~20건)",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=None,
        metavar="SLUG",
        help=(
            "크롤링 카테고리 slug (기본: funding venture-capital Global-news). "
            "예: --categories funding ai bio-healthcare"
        ),
    )
    parser.add_argument(
        "--no-article-body",
        action="store_true",
        help="기사 상세 페이지 크롤링 스킵 (제목·날짜만 수집, 속도 ~30배 향상)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        metavar="SEC",
        help="페이지 요청 간 대기 시간(초) (기본: 1.0)",
    )
    args = parser.parse_args()

    # from_date 파싱
    from_date: datetime | None
    if args.from_date:
        try:
            from_date = datetime.strptime(args.from_date, "%Y-%m-%d").replace(tzinfo=_KST)
        except ValueError:
            parser.error(f"from-date 형식 오류: '{args.from_date}' (YYYY-MM-DD 필요)")
            return
    else:
        from_date = datetime.now(_KST) - timedelta(days=365)

    logger.info(
        "Backfill 시작 | max_pages=%s | from_date=%s | categories=%s | article_body=%s",
        args.max_pages,
        from_date.date(),
        args.categories or "기본값(funding, venture-capital, Global-news)",
        not args.no_article_body,
    )

    result = asyncio.run(
        run_backfill(
            max_pages=args.max_pages,
            from_date=from_date,
            category_slugs=args.categories,
            fetch_article_body=not args.no_article_body,
            sleep_sec=args.sleep,
        )
    )
    _print_result(result)


if __name__ == "__main__":
    main()
