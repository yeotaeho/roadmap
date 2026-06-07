"""식품의약품안전처(MFDS) 보도자료 게시판(`brd/m_99`) 컬렉터 — 바이오/헬스 선행 신호.

전략 (ECONOMIC_FLOW_IMPLEMENTATION_ROADMAP.md §4.2):
  - MFDS 보도자료는 **완전 정적 SSR** → MSIT BBS 패턴을 가볍게 클론.
  - 목록(`list.do?page=N`) 정적 테이블 파싱 → 상세(`view.do?seq=N`) 본문.
  - 필터: **등록일 연도 + 제목 키워드 리스트(any 매칭)** ("허가/신약/임상/품목허가/조건부/승인").
  - 워터마크: `seq`(정수) 또는 source_url.
  - `investment_amount = None` — 정성 트렌드 신호 (raw_metadata.data_role="TREND_SIGNAL").

HTTP/날짜 유틸은 `_msit_common`(브라우저 위장 UA + ConnectionReset 재시도)을 재사용한다.
정부 사이트 게시판 셀렉터는 개편 가능성이 있어 **다중 셀렉터**로 방어한다.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from domain.master.hub.services.collectors.economic.common._msit_common import (
    async_get_html,
    make_async_client,
    parse_kst_date,
)
from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

BASE_URL = "https://www.mfds.go.kr"
_KST = timezone(timedelta(hours=9))

BODY_FETCH_CONCURRENCY = 5

# 신약 허가·임상 등 자본/산업 선행 신호 키워드 (제목에 하나라도 포함되면 채택)
DEFAULT_KEYWORDS: tuple[str, ...] = (
    "허가",
    "신약",
    "임상",
    "품목허가",
    "조건부",
    "승인",
    "지정",
)

_DATE_RE = re.compile(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})")

# 목록 행/제목/날짜 셀렉터 — 개편 대비 다중 후보.
# MFDS 실제 구조(2026-06 실측): div.bbs_list01 > ul > li (기사) / a.title / div.right_column(날짜).
# 첨부 li(ul.bbs_file_list)는 직계 자식(>) 콤비네이터로 제외. table 셀렉터는 폴백·테스트 호환용.
_LIST_ROW_SELECTORS: tuple[str, ...] = (
    "div.bbs_list01 > ul > li",
    "div.bbs_list01 ul > li",
    "ul.bbs_list01 > li",
    "table.board_list tbody tr",
    "table.board_list tr",
    "div.board_list table tbody tr",
    "table.tbl_list tbody tr",
    "table tbody tr",
    "table tr",
)
_TITLE_LINK_SELECTORS: tuple[str, ...] = (
    "div.center_column a.title",
    "a.title",
    "td.title a",
    "td.subject a",
    "td.tit a",
    "td.cont a",
    "a",
)
_DATE_CELL_SELECTORS: tuple[str, ...] = (
    "div.right_column",
    "td.date",
    "td.reg_date",
    "td.regdate",
    "td.day",
    "span.date",
)
_VIEW_CONTENT_SELECTORS: tuple[str, ...] = (
    "div.bv_contents",  # MFDS 실측 본문 컨테이너 (제목+첨부 메타)
    "div.board_view_con",
    "div.view_cont",
    "div.view_con",
    "div.board_view",
    "div.bbs_view",
    "div.cont_area",
    "div.contents",
)


# ---------------------------------------------------------------------------
# board configuration / watermark
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MfdsBoardConfig:
    """MFDS 보도자료 보드 수집 규칙."""

    board_key: str = "mfds_m99"
    list_url: str = f"{BASE_URL}/brd/m_99/list.do"
    view_url: str = f"{BASE_URL}/brd/m_99/view.do"
    source_type: str = "GOVT_MFDS_APPROVAL"
    target_year: int | None = 2026  # None 이면 연도 필터 미적용(전체)
    keywords: tuple[str, ...] = DEFAULT_KEYWORDS
    investor_name: str = "식품의약품안전처"
    industry_sector: str = "BIO"
    signal_priority: str = "P0"


PRESS_BOARD = MfdsBoardConfig()


@dataclass(frozen=True)
class MfdsIngestWatermark:
    """Bronze 증분 기준 — seq(정수) 우선, 보조로 source_url."""

    source_url: str | None = None
    seq: int | None = None


# ---------------------------------------------------------------------------
# parsing helpers (module-level, 단위 테스트 용이)
# ---------------------------------------------------------------------------


def _first_match(root: Tag, selectors: tuple[str, ...]) -> Tag | None:
    for sel in selectors:
        found = root.select_one(sel)
        if found:
            return found
    return None


def extract_seq(href: str, onclick: str, tag: Tag | None = None) -> int | None:
    """게시물 고유 seq 추출 — href 쿼리 → data-* 속성 → onclick/href 의 첫 숫자."""
    if href:
        qs = parse_qs(urlparse(href).query)
        for key in ("seq", "Seq", "SEQ", "brdBltNo", "ntatcSn", "no"):
            vals = qs.get(key)
            if vals and str(vals[0]).isdigit():
                return int(vals[0])
    if tag is not None:
        for attr in ("data-seq", "data-id", "data-no", "data-ntatcsn"):
            v = tag.get(attr)
            if v and str(v).isdigit():
                return int(v)
    for s in (onclick or "", href or ""):
        m = re.search(r"\(\s*['\"]?(\d{2,})", s)
        if m:
            return int(m.group(1))
    return None


def build_view_url(board: MfdsBoardConfig, seq: int) -> str:
    return f"{board.view_url}?seq={seq}"


def parse_mfds_list_rows(html: str, board: MfdsBoardConfig = PRESS_BOARD) -> list[dict[str, Any]]:
    """`brd/m_99/list.do` 결과 → 게시물 dict 목록.

    Returns:
        list of {title, url, seq, published_at(datetime|None), published_year, raw_date}.
        제목 링크/식별자가 없는 행(헤더·공지 더미)은 제외.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[Tag] = []
    for sel in _LIST_ROW_SELECTORS:
        rows = soup.select(sel)
        if rows:
            break

    out: list[dict[str, Any]] = []
    for tr in rows:
        if tr.find_parent("thead"):
            continue
        link = _first_match(tr, _TITLE_LINK_SELECTORS)
        if not link:
            continue
        title = link.get_text(strip=True)
        if not title:
            continue
        href = (link.get("href") or "").strip()
        onclick = link.get("onclick") or ""
        seq = extract_seq(href, onclick, link)

        if seq is not None:
            url = build_view_url(board, seq)
        elif href and not href.lower().startswith("javascript"):
            url = urljoin(BASE_URL, href)
        else:
            continue

        date_cell = _first_match(tr, _DATE_CELL_SELECTORS)
        raw_date = date_cell.get_text(strip=True) if date_cell else ""
        if not raw_date:
            m = _DATE_RE.search(tr.get_text(" ", strip=True))
            raw_date = m.group(0) if m else ""

        pub = parse_kst_date(raw_date)
        out.append(
            {
                "title": title,
                "url": url,
                "seq": seq,
                "published_at": pub,
                "published_year": pub.year if pub else None,
                "raw_date": raw_date,
            }
        )
    return out


def row_matches_keyword(title: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in title for kw in keywords)


# ---------------------------------------------------------------------------
# collector
# ---------------------------------------------------------------------------


class MfdsBbsCollector:
    """MFDS `brd/m_99` 보도자료 정적 게시판 수집기."""

    def __init__(self, board: MfdsBoardConfig = PRESS_BOARD):
        self.board = board

    def collect_sync(
        self,
        *,
        max_pages: int = 5,
        max_items: int = 100,
        fetch_body: bool = True,
        watermark: MfdsIngestWatermark | None = None,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        return asyncio.run(
            self.collect(
                max_pages=max_pages,
                max_items=max_items,
                fetch_body=fetch_body,
                watermark=watermark,
            )
        )

    async def collect(
        self,
        *,
        max_pages: int = 5,
        max_items: int = 100,
        fetch_body: bool = True,
        watermark: MfdsIngestWatermark | None = None,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        last_seq = watermark.seq if watermark else None
        last_url = watermark.source_url if watermark else None

        stats = {
            "fetched_total": 0,
            "filtered_year": 0,
            "filtered_keyword": 0,
            "skipped_watermark": 0,
        }
        kept: list[dict[str, Any]] = []

        async with make_async_client() as client:
            for page in range(1, max_pages + 1):
                url = self._page_url(page)
                logger.info("[%s] page=%s url=%s", self.board.board_key, page, url)
                try:
                    html = await async_get_html(client, url, timeout=30.0)
                except Exception:
                    logger.exception("[%s] list fetch failed page=%s", self.board.board_key, page)
                    break

                rows = parse_mfds_list_rows(html, self.board)
                if not rows:
                    logger.info("[%s] no list rows page=%s — stop", self.board.board_key, page)
                    break

                hit = self._consume_rows(rows, stats, kept, last_seq, last_url, max_items)
                if hit:
                    break
                await asyncio.sleep(0.35)

            dtos = await self._build_dtos(client, kept, fetch_body)

        logger.info("[%s] collected dtos=%s stats=%s", self.board.board_key, len(dtos), stats)
        return dtos, stats

    def _consume_rows(
        self,
        rows: list[dict[str, Any]],
        stats: dict[str, int],
        kept: list[dict[str, Any]],
        last_seq: int | None,
        last_url: str | None,
        max_items: int,
    ) -> bool:
        """필터링·워터마크 적용. 반환 True 면 페이지네이션 중단."""
        for row in rows:
            stats["fetched_total"] += 1

            # 워터마크 — 직전 수집 지점 도달 시 중단(증분)
            if last_seq is not None and row.get("seq") == last_seq:
                stats["skipped_watermark"] += 1
                return True
            if last_url and row.get("url") == last_url:
                stats["skipped_watermark"] += 1
                return True

            # 연도 필터 — 불일치는 continue(공지·고정행이 섞여도 조기 종료 방지, max_pages 로 bound)
            if self.board.target_year is not None:
                if row.get("published_year") != self.board.target_year:
                    stats["filtered_year"] += 1
                    continue

            # 제목 키워드(any) 필터
            if not row_matches_keyword(row["title"], self.board.keywords):
                stats["filtered_keyword"] += 1
                continue

            kept.append(dict(row))
            if len(kept) >= max_items:
                return True
        return False

    async def _build_dtos(
        self,
        client: Any,
        kept: list[dict[str, Any]],
        fetch_body: bool,
    ) -> list[EconomicCollectDto]:
        if not kept:
            return []

        sem = asyncio.Semaphore(BODY_FETCH_CONCURRENCY)

        async def body_for(row: dict[str, Any]) -> str:
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
                return self._extract_main_text(html)

        bodies = await asyncio.gather(*[body_for(dict(r)) for r in kept])
        return [self._to_dto(row, body) for row, body in zip(kept, bodies)]

    def _extract_main_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        node = _first_match(soup, _VIEW_CONTENT_SELECTORS) or soup.body or soup
        text = node.get_text(separator="\n", strip=True)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:20000]

    def _page_url(self, page: int) -> str:
        sep = "&" if "?" in self.board.list_url else "?"
        return f"{self.board.list_url}{sep}{urlencode({'page': page})}"

    def _to_dto(self, row: dict[str, Any], body_text: str) -> EconomicCollectDto:
        raw_metadata: dict[str, Any] = {
            "board_key": self.board.board_key,
            "industry_sector": self.board.industry_sector,
            "signal_priority": self.board.signal_priority,
            "data_role": "TREND_SIGNAL",
            "is_signal": True,
            "filter": {
                "year": self.board.target_year,
                "keywords": list(self.board.keywords),
            },
            "raw_date": row.get("raw_date"),
            "collected_via": "mfds-bbs-crawler",
        }
        seq = row.get("seq")
        if seq is not None:
            raw_metadata["seq"] = seq
        if body_text:
            raw_metadata["body_text"] = body_text
            raw_metadata["body_text_length"] = len(body_text)

        return EconomicCollectDto(
            source_type=self.board.source_type,
            source_url=row["url"],
            raw_title=row["title"][:500],
            investor_name=self.board.investor_name,
            target_company_or_fund=None,
            investment_amount=None,  # 정성 트렌드 신호 — 금액 없음
            currency="KRW",
            raw_metadata=raw_metadata,
            published_at=row.get("published_at"),
        )


def _with_year(cfg: MfdsBoardConfig, target_year: int | None) -> MfdsBoardConfig:
    if target_year == cfg.target_year:
        return cfg
    return MfdsBoardConfig(
        board_key=cfg.board_key,
        list_url=cfg.list_url,
        view_url=cfg.view_url,
        source_type=cfg.source_type,
        target_year=target_year,
        keywords=cfg.keywords,
        investor_name=cfg.investor_name,
        industry_sector=cfg.industry_sector,
        signal_priority=cfg.signal_priority,
    )


def press_collector(*, target_year: int | None = 2026) -> MfdsBbsCollector:
    return MfdsBbsCollector(_with_year(PRESS_BOARD, target_year))


__all__ = [
    "MfdsBoardConfig",
    "MfdsBbsCollector",
    "MfdsIngestWatermark",
    "PRESS_BOARD",
    "press_collector",
    "parse_mfds_list_rows",
    "extract_seq",
    "build_view_url",
    "row_matches_keyword",
]

_ = field  # reserved for future config defaults
