"""Bronze 경제 파이프라인 유스케이스 — 소스별 Collector 호출 후 `raw_economic_data` 적재."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from pathlib import Path

from domain.master.hub.repositories.economic_repository import EconomicRepository
from domain.master.hub.services.collectors.economic.dart_collector import DartEconomicCollector
from domain.master.hub.services.collectors.economic.moef_local_pdf_collector import (
    MoefLocalPdfCollector,
)
from domain.master.hub.services.collectors.economic.msit_bbs_collector import (
    BIZ_BOARD,
    PRESS_BOARD,
    BoardConfig,
    MsitBbsCollector,
    MsitBbsIngestWatermark,
)
from domain.master.hub.services.collectors.economic.msit_publicinfo_63_collector import (
    BOARD_KEY as MSIT_PUBINFO_BOARD_KEY,
    MsitPublicInfo63Collector,
    SOURCE_TYPE as MSIT_PUBINFO_SOURCE_TYPE,
)
from domain.master.hub.services.collectors.economic.msit_watermark import (
    parse_ntt_seq_no_from_url,
)
from domain.master.hub.services.collectors.economic.startup_recipe_collector import (
    StartupRecipeEconomicCollector,
)
from domain.master.hub.services.collectors.economic.platum_collector import (
    PlatumEconomicCollector,
)
from domain.master.hub.services.collectors.economic.wowtale_collector import WowtaleEconomicCollector
from domain.master.hub.services.collectors.economic.yahoo_finance_collector import (
    YahooFinanceEtfCollector,
)
from domain.master.hub.services.collectors.economic.yahoo_macro_collector import (
    YahooMacroCollector,
)
from domain.master.hub.services.collectors.economic.alio_public_inst_project_collector import (
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
    ):
        self._session = session
        self._dart_key = dart_api_key
        self._alio_key = alio_service_key
        self._economic_repo = EconomicRepository(session)

    async def ingest_dart(
        self,
        bgn_de: str | None = None,
        end_de: str | None = None,
        *,
        include_ownership_disclosure: bool = True,
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

    async def purge_by_source_type(self, source_type: str) -> dict[str, Any]:
        deleted = await self._economic_repo.delete_by_source_type(source_type)
        result = {"source_type": source_type, "deleted": deleted}
        logger.info("Bronze economic purge: %s", result)
        return result
