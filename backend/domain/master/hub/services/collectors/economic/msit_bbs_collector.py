"""과기부 BBS 보드(`mId=307` 보도자료 / `mId=311` 사업공고) 공통 컬렉터.

전략:
  - 목록 추출은 `MSITBbsListStrategy` 구현체에 위임 (인라인 JSON / 테이블+div 폴백).
  - `httpx.AsyncClient` + 제한된 병렬도로 목록·본문 GET.
  - 워터마크: 정규화 URL 또는 (`ntt_seq_no`, `published_at`) 동시 일치.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from domain.master.hub.services.collectors.economic._msit_common import (
    BASE_URL,
    _INLINE_SEARCH_DATA_RE,
    async_get_html,
    build_msit_bbs_view_url,
    extract_action_form_params,
    extract_fn_detail_ntt_ids,
    extract_inline_search_result,
    make_async_client,
    parse_bbs_list_rows,
    parse_msit_bbs_view_summary,
    normalize_inline_row,
    today_kst,
)
from domain.master.hub.services.collectors.economic.msit_watermark import (
    bbs_row_matches_watermark,
    normalize_msit_url,
    parse_ntt_seq_no_from_url,
)
from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

LIST_PAGE_CONCURRENCY = 4
BODY_FETCH_CONCURRENCY = 5


# ---------------------------------------------------------------------------
# board configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoardConfig:
    """단일 BBS 보드 수집 규칙."""

    board_key: str
    list_url: str
    source_type: str
    target_year: int
    title_keyword: str
    use_server_search: bool = True
    use_inline_search_json: bool = False
    search_option_code: str = "NTT_SJ"
    investor_name: str = "과학기술정보통신부"


PRESS_BOARD = BoardConfig(
    board_key="msit_bbs_307",
    list_url=f"{BASE_URL}/bbs/list.do?sCode=user&mPid=208&mId=307",
    source_type="GOVT_MSIT_PRESS",
    target_year=2026,
    title_keyword="시행",
    use_server_search=True,
    use_inline_search_json=True,
)

BIZ_BOARD = BoardConfig(
    board_key="msit_bbs_311",
    list_url=f"{BASE_URL}/bbs/list.do?sCode=user&mPid=121&mId=311",
    source_type="GOVT_MSIT_BIZ",
    target_year=2026,
    title_keyword="모집",
    use_server_search=True,
    use_inline_search_json=False,
)


@dataclass(frozen=True)
class MsitBbsIngestWatermark:
    """Bronze 증분 기준 — `source_url` 은 DB 문자열 그대로 넣고 비교 시에만 정규화."""

    source_url: str | None = None
    ntt_seq_no: int | None = None
    published_at: datetime | None = None


# ---------------------------------------------------------------------------
# list strategies
# ---------------------------------------------------------------------------


@runtime_checkable
class MSITBbsListStrategy(Protocol):
    async def fetch_list_rows(
        self,
        client: httpx.AsyncClient,
        board: BoardConfig,
        list_html: str,
        *,
        list_url: str,
    ) -> tuple[list[dict[str, Any]], int | None]:
        """한 페이지 list HTML → 정규화 row dict 목록, (선택) total_count."""
        ...


def _parse_inline_search_html_to_rows(html: str) -> tuple[list[dict[str, Any]], int | None]:
    """`getSerachData()` 인라인 부분 — chompjs 우선, 실패 시 `extract_inline_search_result`."""
    m = _INLINE_SEARCH_DATA_RE.search(html)
    if not m:
        return [], None
    raw = m.group("payload")
    if raw in ('""', "''"):
        return [], 0

    payload_dict: dict[str, Any] | None = None
    chomp_exc = False
    try:
        import chompjs

        data = chompjs.parse_js_object(raw)
        if isinstance(data, dict):
            inner = data.get("result")
            if isinstance(inner, dict):
                payload_dict = inner
            elif "rows" in data:
                payload_dict = data
    except Exception:
        chomp_exc = True
        logger.warning("MSIT inline JSON: chompjs 예외 — regex+json 폴백", exc_info=False)

    if payload_dict is None and not chomp_exc:
        logger.warning("MSIT inline JSON: chompjs 스키마 불일치 — regex+json 폴백")

    if payload_dict is None:
        fallback = extract_inline_search_result(html)
        if not fallback:
            return [], None
        payload_dict = fallback

    rows_in = payload_dict.get("rows") or []
    out: list[dict[str, Any]] = []
    for r in rows_in:
        norm = normalize_inline_row(r)
        if norm:
            out.append(norm)
    return out, payload_dict.get("total_count")


class MSITInlineJsonListStrategy:
    """mId=307 등 — 인라인 JS 객체(`getSerachData`)에서 행 추출."""

    async def fetch_list_rows(
        self,
        client: httpx.AsyncClient,
        board: BoardConfig,
        list_html: str,
        *,
        list_url: str,
    ) -> tuple[list[dict[str, Any]], int | None]:
        _ = client, board, list_url
        return _parse_inline_search_html_to_rows(list_html)


class MSITDivFallbackListStrategy:
    """테이블이 비었을 때 `fn_detail` + `view.do` 로 행 복원."""

    async def expand_from_list_html(
        self,
        client: httpx.AsyncClient,
        board: BoardConfig,
        list_html: str,
    ) -> list[dict[str, Any]]:
        form_params = extract_action_form_params(list_html)
        if not form_params.get("bbsSeqNo"):
            logger.warning(
                "[%s] actionForm 에 bbsSeqNo 없음 — view URL 이 불완전할 수 있음",
                board.board_key,
            )
        ntt_ids = extract_fn_detail_ntt_ids(list_html)
        if not ntt_ids:
            return []

        sem = asyncio.Semaphore(BODY_FETCH_CONCURRENCY)

        async def load_one(ntt: int) -> dict[str, Any] | None:
            async with sem:
                view_url = build_msit_bbs_view_url(form_params, ntt)
                try:
                    vhtml = await async_get_html(client, view_url, timeout=30.0)
                except Exception:
                    logger.exception(
                        "[%s] view fetch failed ntt=%s",
                        board.board_key,
                        ntt,
                    )
                    return None
                title, pub_at, raw_date = parse_msit_bbs_view_summary(vhtml)
                year = pub_at.year if pub_at else None
                if year != board.target_year:
                    if str(board.target_year) in title:
                        year = board.target_year
                    else:
                        return None
                if board.title_keyword not in title:
                    return None
                return {
                    "title": title,
                    "url": view_url,
                    "published_at": pub_at,
                    "published_year": year,
                    "raw_date": raw_date,
                    "ntt_seq_no": ntt,
                    "_prefetched_view_html": vhtml,
                }

        parts = await asyncio.gather(*[load_one(n) for n in ntt_ids])
        return [p for p in parts if p]


class MSITStaticTableListStrategy:
    """SSR `<table>` 목록. 비어 있으면 div 폴백으로 위임."""

    def __init__(self) -> None:
        self._div = MSITDivFallbackListStrategy()

    async def fetch_list_rows(
        self,
        client: httpx.AsyncClient,
        board: BoardConfig,
        list_html: str,
        *,
        list_url: str,
    ) -> tuple[list[dict[str, Any]], int | None]:
        _ = list_url
        rows = parse_bbs_list_rows(list_html)
        if rows:
            return rows, None
        expanded = await self._div.expand_from_list_html(client, board, list_html)
        return expanded, None


def _list_strategy_for(board: BoardConfig) -> MSITBbsListStrategy:
    if board.use_inline_search_json:
        return MSITInlineJsonListStrategy()
    return MSITStaticTableListStrategy()


# ---------------------------------------------------------------------------
# collector
# ---------------------------------------------------------------------------


class MsitBbsCollector:
    """MSIT `bbs/list.do` 보드(`mId=307`·`mId=311`) 공통 수집기."""

    def __init__(self, board: BoardConfig):
        self.board = board

    def collect_sync(
        self,
        *,
        max_pages: int = 6,
        max_items: int = 100,
        fetch_body: bool = True,
        last_seen_url: str | None = None,
        watermark: MsitBbsIngestWatermark | None = None,
        sleep_between_requests: float = 0.5,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        """동기 — 내부적으로 `asyncio.run(self.collect(...))`."""
        _ = sleep_between_requests
        return asyncio.run(
            self.collect(
                max_pages=max_pages,
                max_items=max_items,
                fetch_body=fetch_body,
                last_seen_url=last_seen_url,
                watermark=watermark,
            )
        )

    async def collect(
        self,
        *,
        max_pages: int = 6,
        max_items: int = 100,
        fetch_body: bool = True,
        last_seen_url: str | None = None,
        watermark: MsitBbsIngestWatermark | None = None,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        wm = watermark
        if wm is None and last_seen_url:
            wm = MsitBbsIngestWatermark(source_url=last_seen_url)
        last_norm = normalize_msit_url(wm.source_url) if wm and wm.source_url else None
        last_ntt = wm.ntt_seq_no if wm else None
        last_pub = wm.published_at if wm else None

        strategy = _list_strategy_for(self.board)
        stats = {
            "fetched_total": 0,
            "filtered_year": 0,
            "filtered_keyword": 0,
            "skipped_watermark": 0,
        }
        kept: list[dict[str, Any]] = []

        async with make_async_client() as client:
            page = 1
            html_by_page: dict[int, str] = {}

            while page <= max_pages:
                hi = min(page + LIST_PAGE_CONCURRENCY - 1, max_pages)
                pages_to_load = [p for p in range(page, hi + 1) if p not in html_by_page]
                if pages_to_load:

                    async def _load(p: int) -> tuple[int, str]:
                        u = self._build_page_url(p)
                        h = await async_get_html(client, u, timeout=30.0)
                        return p, h

                    for p, h in await asyncio.gather(*[_load(p) for p in pages_to_load]):
                        html_by_page[p] = h

                list_html = html_by_page.pop(page, "")
                if not list_html:
                    break

                logger.info(
                    "[%s] page=%s url=%s",
                    self.board.board_key,
                    page,
                    self._build_page_url(page),
                )

                try:
                    rows, total = await strategy.fetch_list_rows(
                        client,
                        self.board,
                        list_html,
                        list_url=self._build_page_url(page),
                    )
                except Exception:
                    logger.exception("[%s] list parse/fetch failed page=%s", self.board.board_key, page)
                    break

                if self.board.use_inline_search_json and page == 1 and total is not None:
                    logger.info(
                        "[%s] inline search total=%s (kw=%s)",
                        self.board.board_key,
                        total,
                        self.board.title_keyword,
                    )

                if not rows:
                    logger.info("[%s] no list rows on page=%s — stop", self.board.board_key, page)
                    break

                if self.board.use_inline_search_json:
                    hit = self._consume_inline_rows(
                        rows, stats, kept, last_norm, last_ntt, last_pub, max_items
                    )
                else:
                    hit = self._consume_table_like_rows(
                        rows, stats, kept, last_norm, last_ntt, last_pub, max_items
                    )

                if hit:
                    break
                page += 1
                await asyncio.sleep(0.35)

            dtos = await self._build_dtos(client, kept, fetch_body)

        logger.info("[%s] collected dtos=%s stats=%s", self.board.board_key, len(dtos), stats)
        return dtos, stats

    async def _build_dtos(
        self,
        client: httpx.AsyncClient,
        kept: list[dict[str, Any]],
        fetch_body: bool,
    ) -> list[EconomicCollectDto]:
        if not kept:
            return []

        sem = asyncio.Semaphore(BODY_FETCH_CONCURRENCY)

        async def body_for(row: dict[str, Any]) -> str:
            pref = row.get("_prefetched_view_html")
            if isinstance(pref, str) and pref:
                return self._extract_main_text_from_html(pref)
            if not fetch_body:
                return ""
            url = row.get("url")
            if not isinstance(url, str):
                return ""
            async with sem:
                try:
                    html = await async_get_html(client, url, timeout=30.0)
                except Exception:
                    logger.exception("[%s] body fetch failed url=%s", self.board.board_key, url)
                    return ""
                return self._extract_main_text_from_html(html)

        bodies = await asyncio.gather(*[body_for(dict(r)) for r in kept])
        out: list[EconomicCollectDto] = []
        for row, body_text in zip(kept, bodies):
            r = dict(row)
            r.pop("_prefetched_view_html", None)
            out.append(self._to_dto(r, body_text))
        return out

    def _consume_inline_rows(
        self,
        rows: list[dict[str, Any]],
        stats: dict[str, int],
        kept: list[dict[str, Any]],
        last_norm: str | None,
        last_ntt: int | None,
        last_pub: datetime | None,
        max_items: int,
    ) -> bool:
        hit_watermark = False
        saw_older_year = False

        for row in rows:
            stats["fetched_total"] += 1

            if bbs_row_matches_watermark(
                row,
                last_norm_url=last_norm,
                last_ntt=last_ntt,
                last_published_at=last_pub,
            ):
                stats["skipped_watermark"] += 1
                hit_watermark = True
                break

            year = row.get("published_year")
            if year is not None and year < self.board.target_year:
                saw_older_year = True
                stats["filtered_year"] += 1
                continue

            if year != self.board.target_year:
                stats["filtered_year"] += 1
                continue

            if self.board.title_keyword not in row["title"]:
                stats["filtered_keyword"] += 1
                continue

            kept.append(dict(row))
            if len(kept) >= max_items:
                hit_watermark = True
                break

        if saw_older_year and not hit_watermark:
            hit_watermark = True

        return hit_watermark

    def _consume_table_like_rows(
        self,
        rows: list[dict[str, Any]],
        stats: dict[str, int],
        kept: list[dict[str, Any]],
        last_norm: str | None,
        last_ntt: int | None,
        last_pub: datetime | None,
        max_items: int,
    ) -> bool:
        hit_watermark = False
        for row in rows:
            stats["fetched_total"] += 1

            if bbs_row_matches_watermark(
                row,
                last_norm_url=last_norm,
                last_ntt=last_ntt,
                last_published_at=last_pub,
            ):
                stats["skipped_watermark"] += 1
                hit_watermark = True
                break

            year = row.get("published_year")
            if year != self.board.target_year:
                stats["filtered_year"] += 1
                continue

            if self.board.title_keyword not in row["title"]:
                stats["filtered_keyword"] += 1
                continue

            kept.append(dict(row))
            if len(kept) >= max_items:
                hit_watermark = True
                break
        return hit_watermark

    def _extract_main_text_from_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        candidates = (
            "div.board_view_con",
            "div.board_view",
            "div.view_con",
            "div.view_content",
            "div.bbs_view",
            "div.contents",
        )
        node = None
        for sel in candidates:
            node = soup.select_one(sel)
            if node:
                break
        if not node:
            node = soup.body or soup

        text = node.get_text(separator="\n", strip=True)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:20000]

    def _build_page_url(self, page: int) -> str:
        sep = "&" if "?" in self.board.list_url else "?"
        params: dict[str, str] = {"pageIndex": str(page)}
        if self.board.use_server_search:
            params["searchOpt"] = self.board.search_option_code
            params["searchTxt"] = self.board.title_keyword
        return f"{self.board.list_url}{sep}{urlencode(params, encoding='utf-8')}"

    def _to_dto(self, row: dict[str, Any], body_text: str) -> EconomicCollectDto:
        ntt = row.get("ntt_seq_no")
        if ntt is None and isinstance(row.get("url"), str):
            ntt = parse_ntt_seq_no_from_url(row["url"])

        raw_metadata: dict[str, Any] = {
            "board_key": self.board.board_key,
            "filter": {
                "year": self.board.target_year,
                "title_keyword": self.board.title_keyword,
            },
            "is_signal": True,
            "raw_date": row.get("raw_date"),
            "collected_via": (
                "msit-bbs-inline-json"
                if self.board.use_inline_search_json
                else "msit-bbs-crawler"
            ),
        }
        if ntt is not None:
            raw_metadata["ntt_seq_no"] = ntt

        for k in ("department", "telno", "author", "menu_path", "snippet", "sort_date"):
            v = row.get(k)
            if v:
                raw_metadata[k] = v
        if "has_attach" in row:
            raw_metadata["has_attach"] = bool(row["has_attach"])

        if body_text:
            raw_metadata["body_text"] = body_text
            raw_metadata["body_text_length"] = len(body_text)

        return EconomicCollectDto(
            source_type=self.board.source_type,
            source_url=row["url"],
            raw_title=row["title"][:500],
            investor_name=self.board.investor_name,
            target_company_or_fund=None,
            investment_amount=None,
            currency="KRW",
            raw_metadata=raw_metadata,
            published_at=row.get("published_at"),
        )


def _with_year(cfg: BoardConfig, target_year: int | None) -> BoardConfig:
    if target_year is None or target_year == cfg.target_year:
        return cfg
    return BoardConfig(
        board_key=cfg.board_key,
        list_url=cfg.list_url,
        source_type=cfg.source_type,
        target_year=target_year,
        title_keyword=cfg.title_keyword,
        use_server_search=cfg.use_server_search,
        use_inline_search_json=cfg.use_inline_search_json,
        search_option_code=cfg.search_option_code,
        investor_name=cfg.investor_name,
    )


def press_collector(*, target_year: int | None = None) -> MsitBbsCollector:
    return MsitBbsCollector(_with_year(PRESS_BOARD, target_year))


def biz_collector(*, target_year: int | None = None) -> MsitBbsCollector:
    return MsitBbsCollector(_with_year(BIZ_BOARD, target_year))


__all__ = [
    "BoardConfig",
    "MsitBbsCollector",
    "MsitBbsIngestWatermark",
    "PRESS_BOARD",
    "BIZ_BOARD",
    "press_collector",
    "biz_collector",
    "MSITBbsListStrategy",
    "MSITInlineJsonListStrategy",
    "MSITStaticTableListStrategy",
    "MSITDivFallbackListStrategy",
]

_ = today_kst
