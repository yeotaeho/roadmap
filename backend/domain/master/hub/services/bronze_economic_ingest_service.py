"""Bronze 경제 파이프라인 유스케이스 — 소스별 Collector 호출 후 `raw_economic_data` 적재."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from pathlib import Path

from domain.master.hub.repositories.economic_repository import EconomicRepository
from domain.master.hub.services.collectors.economic.dart.dart_collector import DartEconomicCollector
from domain.master.hub.services.collectors.economic.moef.moef_local_pdf_collector import (
    MoefLocalPdfCollector,
)
from domain.master.hub.services.collectors.economic.msit.msit_bbs_collector import (
    BIZ_BOARD,
    PRESS_BOARD,
    BoardConfig,
    MsitBbsCollector,
    MsitBbsIngestWatermark,
)
from domain.master.hub.services.collectors.economic.msit.msit_publicinfo_63_collector import (
    BOARD_KEY as MSIT_PUBINFO_BOARD_KEY,
    MsitPublicInfo63Collector,
    SOURCE_TYPE as MSIT_PUBINFO_SOURCE_TYPE,
)
from domain.master.hub.services.collectors.economic.msit.msit_watermark import (
    parse_ntt_seq_no_from_url,
)
from domain.master.hub.services.collectors.economic.mfds.mfds_bbs_collector import (
    PRESS_BOARD as MFDS_PRESS_BOARD,
    MfdsBbsCollector,
    MfdsBoardConfig,
    MfdsIngestWatermark,
    _with_year as _mfds_with_year,
)
from domain.master.hub.services.collectors.economic.bok.bok_ecos_collector import (
    BokEcosCollector,
)
from domain.master.hub.services.collectors.economic.subsidy24.subsidy24_collector import (
    Subsidy24Collector,
    Subsidy24Watermark,
)
from domain.master.hub.services.collectors.economic.dart.dart_periodic_collector import (
    DartPeriodicCollector,
)
from domain.master.hub.services.collectors.economic.mss.mss_bbs_collector import (
    MssBbsCollector,
    MssWatermark,
)
from domain.master.hub.services.collectors.economic.startup_recipe.startup_recipe_collector import (
    StartupRecipeEconomicCollector,
)
from domain.master.hub.services.collectors.economic.platum.platum_collector import (
    PlatumEconomicCollector,
)
from domain.master.hub.services.collectors.economic.nps.nps_dart_collector import (
    NpsDartCollector,
    NpsWatermark,
)
from domain.master.hub.services.collectors.economic.dart.dart_ipo_collector import (
    DartIpoCollector,
    DartIpoWatermark,
)
from domain.master.hub.services.collectors.economic.kipris.kipris_patent_collector import (
    KiprisPatentCollector,
    KiprisWatermark,
)
from domain.master.hub.services.collectors.economic.naver.naver_datalab_collector import (
    NaverDatalabCollector,
    NaverDatalabWatermark,
)
from domain.master.hub.services.collectors.economic.naver.naver_search_collector import (
    NaverSearchCollector,
    NaverSearchWatermark,
)
from domain.master.hub.services.collectors.economic.venturesquare.venturesquare_collector import (
    VenturesquareEconomicCollector,
)
from domain.master.hub.services.collectors.economic.wowtale.wowtale_collector import WowtaleEconomicCollector
from domain.master.hub.services.collectors.economic.yahoo.yahoo_finance_collector import (
    YahooFinanceEtfCollector,
)
from domain.master.hub.services.collectors.economic.yahoo.yahoo_macro_collector import (
    YahooMacroCollector,
)
from domain.master.hub.services.collectors.economic.alio.alio_public_inst_project_collector import (
    AlioPublicInstProjectCollector,
)
from domain.master.models.bases.raw_economic_data import RawEconomicData
from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto
from sqlalchemy import select

logger = logging.getLogger(__name__)


def _resolve_board(base: BoardConfig, target_year: int | None) -> BoardConfig:
    """target_year 가 명시되면 BoardConfig 의 연도만 override 한 인스턴스 반환."""
    if target_year is None or target_year == base.target_year:
        return base
    return BoardConfig(
        board_key=base.board_key,
        list_url=base.list_url,
        source_type=base.source_type,
        target_year=target_year,
        title_keyword=base.title_keyword,
        use_server_search=base.use_server_search,
        use_inline_search_json=base.use_inline_search_json,
        search_option_code=base.search_option_code,
        investor_name=base.investor_name,
    )


class BronzeEconomicIngestService:
    def __init__(
        self,
        session: AsyncSession,
        dart_api_key: str | None,
        alio_service_key: str | None = None,
        bok_ecos_api_key: str | None = None,
        subsidy24_service_key: str | None = None,
        naver_client_id: str | None = None,
        naver_client_secret: str | None = None,
        kipris_api_key: str | None = None,
    ):
        self._session = session
        self._dart_key = dart_api_key
        self._alio_key = alio_service_key
        self._bok_ecos_key = bok_ecos_api_key
        self._subsidy24_key = subsidy24_service_key
        self._naver_client_id = naver_client_id
        self._naver_client_secret = naver_client_secret
        self._kipris_key = kipris_api_key
        self._economic_repo = EconomicRepository(session)

    async def ingest_dart(
        self,
        bgn_de: str | None = None,
        end_de: str | None = None,
        *,
        include_ownership_disclosure: bool = False,
    ) -> dict[str, Any]:
        if not self._dart_key:
            raise ValueError("DART_API_KEY(또는 OPENDART_API_KEY)가 설정되어 있지 않습니다.")

        collector = DartEconomicCollector(self._dart_key)
        dtos: list[EconomicCollectDto] = []
        try:
            dtos = await collector.collect(
                bgn_de=bgn_de,
                end_de=end_de,
                include_ownership_disclosure=include_ownership_disclosure,
            )
        except Exception:
            logger.exception(
                "DART 경제 Bronze 수집 실패(한도 초과·점검·네트워크 등). 빈 결과로 진행합니다."
            )

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)

        type_counts = dict(Counter(d.source_type for d in dtos).most_common(40))
        result = {
            "source": "dart",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "include_ownership_disclosure": include_ownership_disclosure,
            "source_type_counts": type_counts,
        }
        logger.info("Bronze economic DART ingest: %s", result)
        return result

    async def ingest_wowtale(
        self,
        *,
        max_items: int = 50,
        fetch_article_if_short: bool = True,
    ) -> dict[str, Any]:
        """Wowtale RSS 피드 기반 스타트업 투자 뉴스 수집."""
        collector = WowtaleEconomicCollector()
        dtos: list[EconomicCollectDto] = []
        skipped_noise = 0
        try:
            dtos, skipped_noise = await collector.collect(
                max_items=max_items,
                fetch_article_if_short=fetch_article_if_short,
            )
        except Exception:
            logger.exception("Wowtale 경제 Bronze 수집 실패. 빈 결과로 진행합니다.")

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)

        result = {
            "source": "wowtale",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "skipped_noise": skipped_noise,
        }
        logger.info("Bronze economic Wowtale ingest: %s", result)
        return result

    async def ingest_wowtale_archive(
        self,
        *,
        max_pages: int = 50,
        from_date: datetime | None = None,
        fetch_article_body: bool = True,
        sleep_sec: float = 1.0,
        categories: list[tuple[str, bool]] | None = None,
    ) -> dict[str, Any]:
        """Wowtale 카테고리 아카이브 크롤링 (Backfill 전용).

        RSS 수집기(ingest_wowtale)가 최근 50건만 제공하는 한계를 보완.
        기본 대상: funding, venture-capital, Global-news 카테고리.

        Args:
            max_pages: 카테고리당 최대 순회 페이지 수 (페이지당 ~20건).
            from_date: 이 날짜 이전 기사에 도달하면 해당 카테고리 수집 중단.
            fetch_article_body: True면 기사 상세 페이지를 추가 GET해 본문 추출.
            sleep_sec: 페이지 요청 간 대기 시간(초).
            categories: (slug, apply_investment_filter) 튜플 리스트.
                        None이면 기본값(funding / venture-capital / Global-news).
        """
        from domain.master.hub.services.collectors.economic.wowtale.wowtale_archive_crawler import (
            WowtaleArchiveCrawler,
        )

        crawler = WowtaleArchiveCrawler(
            sleep_sec=sleep_sec,
            fetch_article_body=fetch_article_body,
        )
        dtos: list[EconomicCollectDto] = []
        try:
            dtos = await crawler.crawl_all(
                categories=categories,
                max_pages=max_pages,
                from_date=from_date,
            )
        except Exception:
            logger.exception("Wowtale 아카이브 크롤링 실패. 빈 결과로 진행합니다.")

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)

        type_counts = dict(Counter(d.source_type for d in dtos).most_common(20))
        result: dict[str, Any] = {
            "source": "wowtale_archive",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "source_type_counts": type_counts,
        }
        logger.info("Bronze economic Wowtale archive ingest: %s", result)
        return result

    async def ingest_platum(
        self,
        *,
        max_items: int = 50,
        fetch_article_if_short: bool = True,
    ) -> dict[str, Any]:
        """Platum 펀딩 RSS 기반 스타트업 투자 뉴스 수집."""
        collector = PlatumEconomicCollector()
        dtos: list[EconomicCollectDto] = []
        skipped_noise = 0
        try:
            dtos, skipped_noise = await collector.collect(
                max_items=max_items,
                fetch_article_if_short=fetch_article_if_short,
            )
        except Exception:
            logger.exception("Platum 경제 Bronze 수집 실패. 빈 결과로 진행합니다.")

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)

        result = {
            "source": "platum",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "skipped_noise": skipped_noise,
        }
        logger.info("Bronze economic Platum ingest: %s", result)
        return result

    async def ingest_startup_recipe(self, *, max_items: int = 50) -> dict[str, Any]:
        """스타트업레시피 RSS 피드 기반 스타트업 투자 뉴스 수집."""
        collector = StartupRecipeEconomicCollector()
        dtos: list[EconomicCollectDto] = []
        skipped_noise = 0
        try:
            dtos, skipped_noise = await collector.collect(max_items=max_items)
        except Exception:
            logger.exception(
                "StartupRecipe 경제 Bronze 수집 실패. 빈 결과로 진행합니다."
            )

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)

        result = {
            "source": "startup_recipe",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "skipped_noise": skipped_noise,
        }
        logger.info("Bronze economic StartupRecipe ingest: %s", result)
        return result

    async def ingest_yahoo_finance(
        self,
        *,
        backfill: bool = False,
        period: str | None = None,
    ) -> dict[str, Any]:
        """Yahoo Finance 거래량 급증(Volume Surge) 신호 수집.

        Args:
            backfill: True면 기간 내 모든 거래일을 스캔해 과거 급증일을 누적 적재(무거움).
            period: ``yfinance`` ``history(period=...)`` (예: ``1y``, ``6mo``). None이면 컬렉터 기본.
        """
        collector = YahooFinanceEtfCollector()
        dtos: list[EconomicCollectDto] = []
        skipped = 0
        try:
            dtos, skipped = await collector.collect(
                backfill=backfill,
                period=period,
            )
        except Exception:
            logger.exception(
                "Yahoo Finance 경제 Bronze 수집 실패. 빈 결과로 진행합니다."
            )

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)

        result = {
            "source": "yahoo_finance",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "skipped_no_signal": skipped,
            "backfill": backfill,
            "period": period or "default",
        }
        logger.info("Bronze economic YahooFinance ingest: %s", result)
        return result

    async def ingest_yahoo_macro(self) -> dict[str, Any]:
        """Yahoo Macro 가격 변동(Price Surge) Z-score 기반 수집.

        대상 (총 8종):
          - FX 3종         (`YAHOO_FX_*`)         — USDKRW / EURKRW / JPYKRW
          - 미 국채금리 2종 (`YAHOO_RATE_*`)       — 10Y / 13W
          - 원자재 2종     (`YAHOO_COMMODITY_*`)  — 금 / WTI 원유
          - 가상자산 1종   (`YAHOO_COMMODITY_BTC`) — 비트코인

        - 알고리즘: `|일간수익률| / 20일 표준편차 ≥ 자산별 임계값(Z=2.0~2.5)`
        - `investment_amount = None`: 가격 변동은 흐름량을 정의할 수 없음
                                       (raw_metadata 에 수익률·Z-score·종가 등 보존)
        """
        collector = YahooMacroCollector()
        dtos: list[EconomicCollectDto] = []
        skipped = 0
        try:
            dtos, skipped = await collector.collect()
        except Exception:
            logger.exception(
                "Yahoo Macro 경제 Bronze 수집 실패. 빈 결과로 진행합니다."
            )

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)

        result = {
            "source": "yahoo_macro",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "skipped_no_signal": skipped,
        }
        logger.info("Bronze economic YahooMacro ingest: %s", result)
        return result

    async def ingest_yahoo_macro_backfill(
        self,
        *,
        period: str | None = None,
    ) -> dict[str, Any]:
        """Yahoo Macro 기간 내 전체 거래일 Z-score 급변동 스캔 (시계열 Backfill).

        `ingest_yahoo_macro` 는 최신 거래일만 확인하지만,
        본 메서드는 슬라이딩 윈도우로 과거 급변동일을 모두 누적한다.

        Args:
            period: yfinance history period (예: ``1y``, ``6mo``). None이면 기본(1y).
        """
        collector = YahooMacroCollector()
        dtos: list[EconomicCollectDto] = []
        failed = 0
        try:
            dtos, failed = await collector.collect(backfill=True, period=period)
        except Exception:
            logger.exception(
                "Yahoo Macro Backfill 수집 실패. 빈 결과로 진행합니다."
            )

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)

        result = {
            "source": "yahoo_macro_backfill",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "failed_tickers": failed,
            "period": period or "default",
        }
        logger.info("Bronze economic YahooMacro backfill: %s", result)
        return result

    async def ingest_venturesquare(
        self,
        *,
        max_items: int = 50,
        fetch_article_if_short: bool = True,
    ) -> dict[str, Any]:
        """벤처스퀘어 RSS 기반 스타트업 투자 뉴스 수집."""
        collector = VenturesquareEconomicCollector()
        dtos: list[EconomicCollectDto] = []
        skipped_noise = 0
        try:
            dtos, skipped_noise = await collector.collect(
                max_items=max_items,
                fetch_article_if_short=fetch_article_if_short,
            )
        except Exception:
            logger.exception("Venturesquare 경제 Bronze 수집 실패. 빈 결과로 진행합니다.")

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)

        result = {
            "source": "venturesquare",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "skipped_noise": skipped_noise,
        }
        logger.info("Bronze economic Venturesquare ingest: %s", result)
        return result

    async def ingest_alio_projects(
        self,
        *,
        max_items: int = 200,
        inst_filter: list[str] | None = None,
        biz_year: int | None = None,
        disable_keyword_filter: bool = False,
    ) -> dict[str, Any]:
        """ALIO(data.go.kr 15125286) 공공기관 사업 메타 → `raw_economic_data`."""
        if not self._alio_key:
            raise ValueError("ALIO_SERVICE_KEY 가 설정되어 있지 않습니다.")

        collector = AlioPublicInstProjectCollector(self._alio_key)
        dtos: list[EconomicCollectDto] = []
        try:
            dtos = await collector.collect(
                max_items=max_items,
                inst_filter=inst_filter,
                biz_year=biz_year,
                disable_keyword_filter=disable_keyword_filter,
            )
        except Exception:
            logger.exception(
                "ALIO 공공기관 사업정보 Bronze 수집 실패(API 오류·네트워크 등). 빈 결과로 진행합니다."
            )

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": "alio_projects",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
        }
        logger.info("Bronze economic ALIO projects ingest: %s", result)
        return result

    # ------------------------------------------------------------------
    # 정부 문서 (전략 A·B) — GOVT_DOCS_COLLECTION_STRATEGY.md 구현
    # ------------------------------------------------------------------

    async def ingest_msit_press(
        self,
        *,
        max_pages: int = 6,
        max_items: int = 100,
        fetch_body: bool = True,
        target_year: int | None = None,
    ) -> dict[str, Any]:
        """과기부 `mId=307` 보도자료 (등록일 연도 + 제목 "시행") 수집."""
        board = _resolve_board(PRESS_BOARD, target_year)
        return await self._ingest_msit_bbs(
            board,
            max_pages=max_pages,
            max_items=max_items,
            fetch_body=fetch_body,
        )

    async def ingest_msit_biz(
        self,
        *,
        max_pages: int = 6,
        max_items: int = 100,
        fetch_body: bool = True,
        target_year: int | None = None,
    ) -> dict[str, Any]:
        """과기부 `mId=311` 사업공고 (등록일 연도 + 제목 "모집") 수집."""
        board = _resolve_board(BIZ_BOARD, target_year)
        return await self._ingest_msit_bbs(
            board,
            max_pages=max_pages,
            max_items=max_items,
            fetch_body=fetch_body,
        )

    async def _ingest_msit_bbs(
        self,
        board: BoardConfig,
        *,
        max_pages: int,
        max_items: int,
        fetch_body: bool,
    ) -> dict[str, Any]:
        # 워터마크: 최신 행의 URL(비교 시 정규화) + raw_metadata.ntt_seq_no + published_at
        # — 쿼리스트링 순서가 바뀌어도 동일 게시물로 인식.
        wm = await self._latest_msit_bbs_watermark(board.source_type)
        collector = MsitBbsCollector(board)

        dtos: list[EconomicCollectDto] = []
        stats: dict[str, int] = {}
        try:
            dtos, stats = await collector.collect(
                max_pages=max_pages,
                max_items=max_items,
                fetch_body=fetch_body,
                watermark=wm,
            )
        except Exception:
            logger.exception(
                "MSIT %s Bronze 수집 실패 (board=%s). 빈 결과로 진행합니다.",
                board.source_type,
                board.board_key,
            )

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": board.board_key,
            "source_type": board.source_type,
            "target_year": board.target_year,
            "title_keyword": board.title_keyword,
            "watermark": (
                {
                    "source_url": wm.source_url,
                    "ntt_seq_no": wm.ntt_seq_no,
                    "published_at": wm.published_at.isoformat() if wm and wm.published_at else None,
                }
                if wm
                else None
            ),
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "stats": stats,
        }
        logger.info("Bronze economic MSIT BBS ingest: %s", result)
        return result

    async def ingest_msit_rnd_budget(
        self,
        *,
        max_pages: int = 2,
        max_items: int = 20,
    ) -> dict[str, Any]:
        """과기부 `mId=63` 예산 및 결산 — HWPX 자동 다운로드·파싱."""
        last_seen_seq = await self._latest_publict_list_seq_no()
        collector = MsitPublicInfo63Collector()

        dtos: list[EconomicCollectDto] = []
        stats: dict[str, int] = {}
        try:
            dtos, stats = await collector.collect(
                max_pages=max_pages,
                max_items=max_items,
                last_seen_list_seq_no=last_seen_seq,
            )
        except Exception:
            logger.exception(
                "MSIT publicinfo(mId=63) 수집 실패. 빈 결과로 진행합니다."
            )

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": MSIT_PUBINFO_BOARD_KEY,
            "source_type": MSIT_PUBINFO_SOURCE_TYPE,
            "watermark_last_seen_seq": last_seen_seq,
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "stats": stats,
        }
        logger.info("Bronze economic MSIT publicinfo-63 ingest: %s", result)
        return result

    async def ingest_mfds_press(
        self,
        *,
        max_pages: int = 5,
        max_items: int = 100,
        fetch_body: bool = True,
        target_year: int | None = None,
    ) -> dict[str, Any]:
        """식약처(MFDS) 보도자료 (연도 + 허가/신약/임상 키워드) 수집 → `raw_economic_data`.

        바이오/헬스 선행 신호(GOVT_MFDS_APPROVAL). investment_amount=None (정성 신호).
        """
        board: MfdsBoardConfig = (
            MFDS_PRESS_BOARD if target_year is None else _mfds_with_year(MFDS_PRESS_BOARD, target_year)
        )
        wm = await self._latest_mfds_watermark(board.source_type)
        collector = MfdsBbsCollector(board)

        dtos: list[EconomicCollectDto] = []
        stats: dict[str, int] = {}
        try:
            dtos, stats = await collector.collect(
                max_pages=max_pages,
                max_items=max_items,
                fetch_body=fetch_body,
                watermark=wm,
            )
        except Exception:
            logger.exception("MFDS 보도자료 Bronze 수집 실패. 빈 결과로 진행합니다.")

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": board.board_key,
            "source_type": board.source_type,
            "target_year": board.target_year,
            "watermark": (
                {"source_url": wm.source_url, "seq": wm.seq} if wm else None
            ),
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "stats": stats,
        }
        logger.info("Bronze economic MFDS press ingest: %s", result)
        return result

    async def ingest_bok_ecos(
        self,
        *,
        start: str,
        end: str,
        max_rows: int = 10000,
    ) -> dict[str, Any]:
        """한국은행 ECOS 거시 시계열(FDI·통화량·기준금리) → `raw_economic_data`.

        Args:
            start/end: 주기별 일자 문자열 — 월 YYYYMM / 연 YYYY / 일 YYYYMMDD / 분기 YYYYQn.
        """
        if not self._bok_ecos_key:
            raise ValueError("BOK_ECOS_API_KEY 가 설정되어 있지 않습니다.")

        collector = BokEcosCollector(self._bok_ecos_key)
        dtos: list[EconomicCollectDto] = []
        try:
            dtos = await collector.collect(start=start, end=end, max_rows=max_rows)
        except Exception:
            logger.exception("BOK ECOS Bronze 수집 실패. 빈 결과로 진행합니다.")

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        type_counts = dict(Counter(d.source_type for d in dtos).most_common(20))
        result = {
            "source": "bok_ecos",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "source_type_counts": type_counts,
            "range": {"start": start, "end": end},
        }
        logger.info("Bronze economic BOK ECOS ingest: %s", result)
        return result

    async def ingest_subsidy24(
        self,
        *,
        max_items: int = 500,
    ) -> dict[str, Any]:
        """보조금24(gov24) 정부 지원 서비스 목록 → `raw_economic_data`.

        증분 수집: DB 최신 `수정일시` → cond[수정일시:GTE] API 파라미터로 변경분만 가져온다.
        """
        if not self._subsidy24_key:
            raise ValueError("SUBSIDY24_SERVICE_KEY 가 설정되어 있지 않습니다.")

        wm = await self._latest_subsidy24_watermark()
        collector = Subsidy24Collector(self._subsidy24_key)

        dtos: list[EconomicCollectDto] = []
        stats: dict[str, int] = {}
        try:
            dtos, stats = await collector.collect(max_items=max_items, watermark=wm)
        except Exception:
            logger.exception("보조금24 Bronze 수집 실패. 빈 결과로 진행합니다.")

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result: dict[str, Any] = {
            "source": "subsidy24",
            "watermark": wm.modified_at.isoformat() if wm and wm.modified_at else None,
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "stats": stats,
        }
        logger.info("Bronze economic 보조금24 ingest: %s", result)
        return result

    async def ingest_dart_periodic(
        self,
        bgn_de: str | None = None,
        end_de: str | None = None,
        *,
        enrich_financials: bool = True,
        max_enrich: int = 200,
    ) -> dict[str, Any]:
        """DART 정기공시(A) 사업보고서·반기보고서 → `raw_economic_data`.

        R&D/CAPEX 금액 보강(enrich_financials=True, KOSPI/KOSDAQ 법인 우선).
        """
        if not self._dart_key:
            raise ValueError("DART_API_KEY(또는 OPENDART_API_KEY)가 설정되어 있지 않습니다.")

        collector = DartPeriodicCollector(self._dart_key)
        dtos: list[EconomicCollectDto] = []
        stats: dict[str, int] = {}
        try:
            dtos, stats = await collector.collect(
                bgn_de=bgn_de,
                end_de=end_de,
                enrich_financials=enrich_financials,
                max_enrich=max_enrich,
            )
        except Exception:
            logger.exception("DART 정기공시 Bronze 수집 실패. 빈 결과로 진행합니다.")

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        type_counts = dict(Counter(d.source_type for d in dtos).most_common(10))
        result: dict[str, Any] = {
            "source": "dart_periodic",
            "bgn_de": bgn_de,
            "end_de": end_de,
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "source_type_counts": type_counts,
            "stats": stats,
        }
        logger.info("Bronze economic DART 정기공시 ingest: %s", result)
        return result

    async def ingest_mss_press(
        self,
        *,
        max_items: int = 200,
    ) -> dict[str, Any]:
        """중소벤처기업부(MSS) 보도자료 → `raw_economic_data`.

        창업·벤처·중소기업 정책 선행 신호(GOVT_MSS_PRESS).
        증분 수집: DB 최신 bcIdx 워터마크 이하 항목은 skip.
        """
        wm = await self._latest_mss_watermark()
        collector = MssBbsCollector()

        dtos: list[EconomicCollectDto] = []
        stats: dict[str, int] = {}
        try:
            dtos, stats = await collector.collect(max_items=max_items, watermark=wm)
        except Exception:
            logger.exception("중기부 보도자료 Bronze 수집 실패. 빈 결과로 진행합니다.")

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result: dict[str, Any] = {
            "source": "mss_press",
            "source_type": "GOVT_MSS_PRESS",
            "watermark": {"bc_idx": wm.bc_idx} if wm else None,
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "stats": stats,
        }
        logger.info("Bronze economic MSS 보도자료 ingest: %s", result)
        return result

    async def ingest_moef_local_pdfs(
        self,
        paths: list[Path | str],
        *,
        source_type: str | None = None,
        published_at: Any | None = None,
        source_url: str | None = None,
        raw_title: str | None = None,
        original_filename: str | None = None,
    ) -> dict[str, Any]:
        """기재부 거시 예산안·국가재정운용계획 — 로컬 PDF 시드/업로드 적재.

        업로드 시나리오에서는 라우터가 tmp_dir 의 UUID 파일명으로 저장하므로,
        ``original_filename`` (또는 ``raw_title``) 을 명시적으로 넘겨야 사람이 읽을 수 있는
        제목이 남는다. 시드 배치(여러 파일)에서는 None 권장.
        """
        collector = MoefLocalPdfCollector()
        dtos: list[EconomicCollectDto] = []
        stats: dict[str, int] = {}
        try:
            dtos, stats = await asyncio.to_thread(
                collector.collect_paths,
                [Path(p) for p in paths],
                source_type=source_type,
                published_at=published_at,
                source_url=source_url,
                raw_title=raw_title,
                original_filename=original_filename,
            )
        except Exception:
            logger.exception("MOEF local PDF 수집 실패. 빈 결과로 진행합니다.")

        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": "moef_local_pdf",
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": max(0, len(dtos) - inserted),
            "stats": stats,
        }
        logger.info("Bronze economic MOEF local PDF ingest: %s", result)
        return result

    # --- watermark helpers --------------------------------------------------

    async def _latest_source_url(self, source_type: str) -> str | None:
        """동일 source_type 에서 가장 최근 적재된 source_url 1개 (게시일 기준)."""
        stmt = (
            select(RawEconomicData.source_url)
            .where(RawEconomicData.source_type == source_type)
            .order_by(RawEconomicData.published_at.desc().nullslast())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _latest_msit_bbs_watermark(self, source_type: str) -> MsitBbsIngestWatermark | None:
        """MSIT BBS 증분 기준.

        DB `source_url` 은 적재 시점 문자열을 유지하고, 컬렉터에서는 `normalize_msit_url`
        로 비교한다. 구 레코드에 `raw_metadata.ntt_seq_no` 가 없으면 URL 쿼리에서 파싱한다.
        """
        stmt = (
            select(
                RawEconomicData.source_url,
                RawEconomicData.published_at,
                RawEconomicData.raw_metadata,
            )
            .where(RawEconomicData.source_type == source_type)
            .order_by(RawEconomicData.published_at.desc().nullslast())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).mappings().first()
        if not row or not row.get("source_url"):
            return None
        meta = row.get("raw_metadata") or {}
        ntt = meta.get("ntt_seq_no") if isinstance(meta, dict) else None
        if isinstance(ntt, str) and ntt.isdigit():
            ntt = int(ntt)
        if not isinstance(ntt, int):
            ntt = None
        url = row["source_url"]
        if ntt is None and isinstance(url, str):
            ntt = parse_ntt_seq_no_from_url(url)
        return MsitBbsIngestWatermark(
            source_url=url,
            ntt_seq_no=ntt,
            published_at=row.get("published_at"),
        )

    async def _latest_mfds_watermark(self, source_type: str) -> MfdsIngestWatermark | None:
        """MFDS 증분 기준 — 최신 published_at 행의 source_url + raw_metadata.seq."""
        stmt = (
            select(
                RawEconomicData.source_url,
                RawEconomicData.raw_metadata,
            )
            .where(RawEconomicData.source_type == source_type)
            .order_by(RawEconomicData.published_at.desc().nullslast())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).mappings().first()
        if not row or not row.get("source_url"):
            return None
        meta = row.get("raw_metadata") or {}
        seq = meta.get("seq") if isinstance(meta, dict) else None
        if isinstance(seq, str) and seq.isdigit():
            seq = int(seq)
        if not isinstance(seq, int):
            seq = None
        return MfdsIngestWatermark(source_url=row["source_url"], seq=seq)

    async def _latest_publict_list_seq_no(self) -> int | None:
        """`GOVT_MSIT_RND` 의 raw_metadata.publict_list_seq_no MAX.

        Postgres jsonb 연산자(`->>`) 로 정수 캐스팅 후 정렬한다.
        """
        from sqlalchemy import Integer, cast, func

        meta = RawEconomicData.raw_metadata
        stmt = (
            select(func.max(cast(meta["publict_list_seq_no"].astext, Integer)))
            .where(RawEconomicData.source_type == MSIT_PUBINFO_SOURCE_TYPE)
        )
        try:
            result = await self._session.execute(stmt)
            value = result.scalar_one_or_none()
            return int(value) if value is not None else None
        except Exception:
            # JSONB 미지원 DB(SQLite 등) 환경에서도 컬렉터 자체는 진행 가능
            logger.exception(
                "publict_list_seq_no 워터마크 조회 실패 — full re-fetch 로 진행"
            )
            return None

    async def _latest_mss_watermark(self) -> MssWatermark | None:
        """중기부 증분 기준 — DB 최신 raw_metadata.bc_idx."""
        stmt = (
            select(RawEconomicData.raw_metadata)
            .where(RawEconomicData.source_type == "GOVT_MSS_PRESS")
            .order_by(RawEconomicData.published_at.desc().nullslast())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if not row:
            return None
        meta = row if isinstance(row, dict) else {}
        bc_idx = meta.get("bc_idx") if isinstance(meta, dict) else None
        if bc_idx is not None:
            try:
                bc_idx = int(bc_idx)
            except (TypeError, ValueError):
                bc_idx = None
        return MssWatermark(bc_idx=bc_idx) if bc_idx else None

    async def _latest_subsidy24_watermark(self) -> Subsidy24Watermark | None:
        """보조금24 증분 기준 — DB 에서 가장 최근 `수정일시`(raw_metadata.modified_at_raw) 추출."""
        stmt = (
            select(RawEconomicData.raw_metadata)
            .where(RawEconomicData.source_type == "GOVT_SUBSIDY24")
            .order_by(RawEconomicData.published_at.desc().nullslast())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if not row:
            return None
        meta = row if isinstance(row, dict) else {}
        raw_dt_str = meta.get("modified_at_raw") if isinstance(meta, dict) else None
        if not raw_dt_str:
            return None
        from domain.master.hub.services.collectors.economic.subsidy24.subsidy24_collector import (
            parse_modified_at as _parse_modified_at,
        )
        dt = _parse_modified_at(raw_dt_str)
        return Subsidy24Watermark(modified_at=dt) if dt else None

    # ------------------------------------------------------------------
    # DART IPO 발행공시 (pblntf_ty=C)
    # ------------------------------------------------------------------

    async def ingest_dart_ipo(
        self,
        *,
        bgn_de: str | None = None,
        end_de: str | None = None,
        max_pages: int = 10,
    ) -> dict[str, Any]:
        """DART 발행공시(C)에서 증권신고서(주식) 등 IPO 선행 신호 수집.

        단일 쿼리 날짜 범위는 14일 이하로 유지 (DART API 제한).
        """
        if not self._dart_key:
            raise ValueError("dart_api_key가 설정되지 않았습니다.")

        from datetime import timedelta
        kst = timezone(timedelta(hours=9))
        today = datetime.now(tz=kst)
        end = end_de or today.strftime("%Y%m%d")
        bgn = bgn_de or (today - timedelta(days=7)).strftime("%Y%m%d")

        wm = await self._latest_dart_ipo_watermark()
        collector = DartIpoCollector(self._dart_key)
        dtos, stats = await collector.collect(
            bgn_de=bgn, end_de=end, watermark=wm, max_pages=max_pages,
        )
        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": "dart_ipo",
            "source_type": "DART_IPO_DISCLOSURE",
            "date_range": {"bgn_de": bgn, "end_de": end},
            "watermark": {"last_rcept_dt": wm.last_rcept_dt} if wm else None,
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": len(dtos) - inserted,
            "stats": stats,
        }
        logger.info("Bronze DART IPO ingest: %s", result)
        return result

    async def _latest_dart_ipo_watermark(self) -> DartIpoWatermark | None:
        """IPO 공시 증분 기준 — DB 최신 raw_metadata.rcept_dt."""
        stmt = (
            select(RawEconomicData.raw_metadata)
            .where(RawEconomicData.source_type == "DART_IPO_DISCLOSURE")
            .order_by(RawEconomicData.published_at.desc().nullslast())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if not row:
            return None
        meta = row if isinstance(row, dict) else {}
        rcept_dt = meta.get("rcept_dt") if isinstance(meta, dict) else None
        return DartIpoWatermark(last_rcept_dt=rcept_dt) if rcept_dt else None

    # ------------------------------------------------------------------
    # 국민연금공단 포트폴리오 (DART 지분공시)
    # ------------------------------------------------------------------

    async def ingest_nps_portfolio(
        self,
        *,
        bgn_de: str | None = None,
        end_de: str | None = None,
        max_pages: int = 30,
    ) -> dict[str, Any]:
        """DART 지분공시(pblntf_ty=D)에서 국민연금공단 대량보유 변동 공시 수집.

        Args:
            bgn_de: 시작일 YYYYMMDD (기본: 오늘 -14일)
            end_de: 종료일 YYYYMMDD (기본: 오늘)
            max_pages: DART API 페이지 상한
        """
        if not self._dart_key:
            raise ValueError("dart_api_key가 설정되지 않았습니다.")

        from datetime import timedelta
        kst = timezone(timedelta(hours=9))
        today = datetime.now(tz=kst)
        end = end_de or today.strftime("%Y%m%d")
        bgn = bgn_de or (today - timedelta(days=14)).strftime("%Y%m%d")

        wm = await self._latest_nps_watermark()
        collector = NpsDartCollector(self._dart_key)
        dtos, stats = await collector.collect(
            bgn_de=bgn, end_de=end, watermark=wm, max_pages=max_pages,
        )
        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result = {
            "source": "nps_portfolio",
            "source_type": "NPS_PORTFOLIO_DART",
            "date_range": {"bgn_de": bgn, "end_de": end},
            "watermark": {"last_rcept_dt": wm.last_rcept_dt} if wm else None,
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": len(dtos) - inserted,
            "stats": stats,
        }
        logger.info("Bronze NPS portfolio ingest: %s", result)
        return result

    async def _latest_nps_watermark(self) -> NpsWatermark | None:
        """NPS 증분 기준 — DB 최신 raw_metadata.rcept_dt."""
        stmt = (
            select(RawEconomicData.raw_metadata)
            .where(RawEconomicData.source_type == "NPS_PORTFOLIO_DART")
            .order_by(RawEconomicData.published_at.desc().nullslast())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if not row:
            return None
        meta = row if isinstance(row, dict) else {}
        rcept_dt = meta.get("rcept_dt") if isinstance(meta, dict) else None
        return NpsWatermark(last_rcept_dt=rcept_dt) if rcept_dt else None

    # ------------------------------------------------------------------
    # 네이버 DataLab 검색량 트렌드 (분야별 주간 실제 검색 수요)
    # ------------------------------------------------------------------

    async def ingest_naver_datalab(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """네이버 DataLab API로 분야별 주간 검색량 비율 수집.

        Args:
            start_date: YYYYMMDD (기본: 오늘-28일). 과거 값 지정 시 backfill.
            end_date:   YYYYMMDD (기본: 오늘)
        """
        if not self._naver_client_id or not self._naver_client_secret:
            raise ValueError("naver_client_id / naver_client_secret 가 설정되지 않았습니다.")

        wm = await self._latest_naver_datalab_watermark()
        collector = NaverDatalabCollector(self._naver_client_id, self._naver_client_secret)
        dtos, stats = await collector.collect(
            start_date=start_date,
            end_date=end_date,
            watermark=wm,
        )
        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result: dict[str, Any] = {
            "source": "naver_datalab",
            "source_type": "DISCOURSE_NAVER_DATALAB",
            "watermark": {"last_week_start": wm.last_week_start} if wm else None,
            "date_range": {"start_date": start_date, "end_date": end_date},
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": len(dtos) - inserted,
            "stats": stats,
        }
        logger.info("Bronze Naver DataLab ingest: %s", result)
        return result

    async def _latest_naver_datalab_watermark(self) -> NaverDatalabWatermark | None:
        """DataLab 증분 기준 — DB 최신 raw_metadata.week_start."""
        stmt = (
            select(RawEconomicData.raw_metadata)
            .where(RawEconomicData.source_type == "DISCOURSE_NAVER_DATALAB")
            .order_by(RawEconomicData.published_at.desc().nullslast())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if not row:
            return None
        meta = row if isinstance(row, dict) else {}
        week_start = meta.get("week_start") if isinstance(meta, dict) else None
        return NaverDatalabWatermark(last_week_start=week_start) if week_start else None

    # ------------------------------------------------------------------
    # KIPRIS 특허 출원 트렌드 (기술 분야별 주간 선행 신호)
    # ------------------------------------------------------------------

    async def ingest_kipris_patents(self) -> dict[str, Any]:
        """KIPRIS PLUS API로 기술 키워드별 주간 특허 출원 건수 수집.

        월 1,000건 한도 → 20키워드 × 주 1회 = ~80건/월.
        주 단위 watermark: 이번 주 이미 수집했으면 skip.
        """
        if not self._kipris_key:
            raise ValueError("KIPRIS_API_KEY(kipris_api_key)가 설정되지 않았습니다.")

        wm = await self._latest_kipris_watermark()
        collector = KiprisPatentCollector(self._kipris_key)
        dtos, stats = await collector.collect(watermark=wm)
        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result: dict[str, Any] = {
            "source": "kipris_patents",
            "source_type": "PATENT_KIPRIS_TREND",
            "watermark": {"last_week_start": wm.last_week_start} if wm else None,
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": len(dtos) - inserted,
            "stats": stats,
        }
        logger.info("Bronze KIPRIS 특허 트렌드 ingest: %s", result)
        return result

    async def _latest_kipris_watermark(self) -> KiprisWatermark | None:
        """KIPRIS 증분 기준 — DB 최신 raw_metadata.week_start."""
        stmt = (
            select(RawEconomicData.raw_metadata)
            .where(RawEconomicData.source_type == "PATENT_KIPRIS_TREND")
            .order_by(RawEconomicData.published_at.desc().nullslast())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if not row:
            return None
        meta = row if isinstance(row, dict) else {}
        week_start = meta.get("week_start") if isinstance(meta, dict) else None
        return KiprisWatermark(last_week_start=week_start) if week_start else None

    # ------------------------------------------------------------------
    # 네이버 뉴스 기사 수 (키워드별 일별 언론 공급 신호)
    # ------------------------------------------------------------------

    async def ingest_naver_search(
        self,
        *,
        target_date: str | None = None,
    ) -> dict[str, Any]:
        """네이버 뉴스 API로 키워드별 일별 기사 수(total) 수집.

        DataLab(주간 검색 수요)과 짝을 이루는 일별 언론 공급(supply) 신호.

        Args:
            target_date: YYYYMMDD (기본: 어제). 과거 날짜 지정 시 backfill.
        """
        if not self._naver_client_id or not self._naver_client_secret:
            raise ValueError("naver_client_id / naver_client_secret 가 설정되지 않았습니다.")

        wm = await self._latest_naver_search_watermark()
        collector = NaverSearchCollector(self._naver_client_id, self._naver_client_secret)
        dtos, stats = await collector.collect(target_date=target_date, watermark=wm)
        inserted = await self._economic_repo.insert_many_skip_duplicates(dtos)
        result: dict[str, Any] = {
            "source": "naver_search",
            "source_type": "DISCOURSE_NAVER_NEWS",
            "watermark": {"last_collected_date": wm.last_collected_date} if wm else None,
            "target_date": target_date,
            "fetched": len(dtos),
            "inserted": inserted,
            "not_inserted": len(dtos) - inserted,
            "stats": stats,
        }
        logger.info("Bronze Naver News Search ingest: %s", result)
        return result

    async def _latest_naver_search_watermark(self) -> NaverSearchWatermark | None:
        """뉴스 검색 증분 기준 — DB 최신 raw_metadata.date."""
        stmt = (
            select(RawEconomicData.raw_metadata)
            .where(RawEconomicData.source_type == "DISCOURSE_NAVER_NEWS")
            .order_by(RawEconomicData.published_at.desc().nullslast())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if not row:
            return None
        meta = row if isinstance(row, dict) else {}
        date_str = meta.get("date") if isinstance(meta, dict) else None
        return NaverSearchWatermark(last_collected_date=date_str) if date_str else None

    async def purge_by_source_type(self, source_type: str) -> dict[str, Any]:
        deleted = await self._economic_repo.delete_by_source_type(source_type)
        result = {"source_type": source_type, "deleted": deleted}
        logger.info("Bronze economic purge: %s", result)
        return result
