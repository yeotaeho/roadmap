"""Yahoo Finance / Yahoo Macro 과거 데이터 Backfill CLI.

슬라이딩 윈도우로 기간 내 모든 거래일을 스캔해 급증/급변동 신호를
`raw_economic_data` 에 누적 적재한다.

사용법::

    cd backend

    # Yahoo Finance (거래량 급증) 1년 Backfill
    python scripts/yahoo_backfill.py --mode finance

    # Yahoo Macro (Z-score 급변동) 1년 Backfill
    python scripts/yahoo_backfill.py --mode macro

    # 둘 다 실행
    python scripts/yahoo_backfill.py --mode all

    # 기간 지정 (6개월)
    python scripts/yahoo_backfill.py --mode all --period 6mo

예상 소요 시간:
    Finance (16 ticker × 250일) : 약 3~5분 (sleep=0.5s 포함)
    Macro   ( 8 ticker × 250일) : 약 1~2분 (sleep=0.5s 포함)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
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
logger = logging.getLogger("yahoo_backfill")


def _print_result(label: str, result: dict) -> None:
    print("\n" + "=" * 60)
    print(f"  {label} Backfill 결과")
    print("=" * 60)
    print(f"  수집 건수   : {result.get('fetched', 0):,}건")
    print(f"  신규 삽입   : {result.get('inserted', 0):,}건")
    print(f"  중복 스킵   : {result.get('not_inserted', 0):,}건")
    if "skipped_no_signal" in result:
        print(f"  신호 없음   : {result['skipped_no_signal']:,}건")
    if "failed_tickers" in result:
        print(f"  실패 티커   : {result['failed_tickers']}개")
    print(f"  period      : {result.get('period', 'N/A')}")
    print("=" * 60 + "\n")


async def run_finance_backfill(period: str | None) -> dict:
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None)
        return await svc.ingest_yahoo_finance(backfill=True, period=period)


async def run_macro_backfill(period: str | None) -> dict:
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None)
        return await svc.ingest_yahoo_macro_backfill(period=period)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Yahoo Finance / Macro 과거 급증 데이터 Backfill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["finance", "macro", "all"],
        default="all",
        help="실행 모드: finance(거래량 급증) / macro(Z-score 급변동) / all(둘 다). 기본: all",
    )
    parser.add_argument(
        "--period",
        default=None,
        metavar="PERIOD",
        help="yfinance history period (예: 1y, 6mo, 3mo). 기본: 1y",
    )
    args = parser.parse_args()

    logger.info(
        "Yahoo Backfill 시작 | mode=%s | period=%s",
        args.mode,
        args.period or "기본(1y)",
    )

    if args.mode in ("finance", "all"):
        logger.info("Yahoo Finance (거래량 급증) Backfill 실행 중...")
        result = asyncio.run(run_finance_backfill(args.period))
        _print_result("Yahoo Finance", result)

    if args.mode in ("macro", "all"):
        logger.info("Yahoo Macro (Z-score 급변동) Backfill 실행 중...")
        result = asyncio.run(run_macro_backfill(args.period))
        _print_result("Yahoo Macro", result)

    logger.info("Backfill 완료")


if __name__ == "__main__":
    main()
