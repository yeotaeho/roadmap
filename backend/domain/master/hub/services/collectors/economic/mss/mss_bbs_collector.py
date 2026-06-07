"""중소벤처기업부(MSS) 보도자료 컬렉터 — 창업·벤처·중소기업 정책 선행 신호.

수집 대상:
  https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=86
  cbIdx=86 = 보도자료 BBS

watermark: 마지막으로 수집한 bcIdx (내림차순 — 높을수록 최신)
  - 1차 실행: max_items 개수만큼 수집 후 최대 bcIdx 저장
  - 이후 실행: 저장된 bcIdx 이하가 나오면 중단

금액 추출: 제목에서 억원·만원 등 한국어 금액 파싱 (parse_krw_amount 재사용)
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto
from domain.master.hub.services.collectors.economic.subsidy24.subsidy24_collector import (
    parse_krw_amount,
)

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))

_BASE_LIST_URL = "https://www.mss.go.kr/site/smba/ex/bbs/List.do"
_BASE_VIEW_URL = "https://www.mss.go.kr/site/smba/ex/bbs/View.do"
_CB_IDX = "86"
_SOURCE_TYPE = "GOVT_MSS_PRESS"
_INVESTOR_NAME = "중소벤처기업부"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.mss.go.kr/",
}

_BC_IDX_RE = re.compile(r"doBbsFView\('86','(\d+)'")


@dataclass(frozen=True)
class MssWatermark:
    bc_idx: int | None = None


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=_KST)
        except ValueError:
            continue
    return None


def _parse_list_page(html: str) -> list[dict[str, Any]]:
    """BBS 목록 HTML → 보도자료 항목 리스트."""
    soup = BeautifulSoup(html, "html.parser")
    result: list[dict[str, Any]] = []
    for row in soup.select("table tbody tr"):
        tds = row.find_all("td")
        if len(tds) < 5:
            continue
        onclick = row.get("onclick") or ""
        m = _BC_IDX_RE.search(onclick)
        if not m:
            continue
        bc_idx = int(m.group(1))
        title = tds[1].get_text(strip=True)
        dept = tds[2].get_text(strip=True)
        date_str = tds[4].get_text(strip=True)
        result.append(
            {
                "bc_idx": bc_idx,
                "title": title,
                "dept": dept,
                "date_str": date_str,
            }
        )
    return result


class MssBbsCollector:
    """중기부 보도자료 BBS 컬렉터."""

    async def collect(
        self,
        *,
        max_items: int = 200,
        watermark: MssWatermark | None = None,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        """보도자료 수집.

        Args:
            max_items: 최대 수집 건수 (기본 200).
            watermark: 이전 실행 워터마크 — bc_idx 이하 항목은 skip.

        Returns:
            (dtos, stats)
        """
        stats: dict[str, int] = {
            "pages_fetched": 0,
            "fetched_total": 0,
            "skipped_watermark": 0,
            "converted": 0,
        }
        prev_bc_idx = watermark.bc_idx if watermark else None
        items: list[dict[str, Any]] = []
        stop = False

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(headers=_HEADERS) as session:
            page_no = 1
            while not stop and len(items) < max_items:
                url = f"{_BASE_LIST_URL}?cbIdx={_CB_IDX}&nPage={page_no}"
                try:
                    async with session.get(url, timeout=timeout) as r:
                        html = await r.text(encoding="utf-8", errors="ignore")
                except Exception as exc:
                    logger.warning("[mss_bbs] 목록 페이지 %s 오류: %s", page_no, exc)
                    break

                page_items = _parse_list_page(html)
                stats["pages_fetched"] += 1

                if not page_items:
                    break

                for item in page_items:
                    stats["fetched_total"] += 1
                    if prev_bc_idx is not None and item["bc_idx"] <= prev_bc_idx:
                        stats["skipped_watermark"] += 1
                        stop = True
                        break
                    items.append(item)
                    if len(items) >= max_items:
                        break

                page_no += 1

        dtos = [self._to_dto(item) for item in items]
        stats["converted"] = len(dtos)
        logger.info("[mss_bbs] pages=%s fetched=%s dtos=%s", stats["pages_fetched"], stats["fetched_total"], len(dtos))
        return dtos, stats

    @staticmethod
    def _to_dto(item: dict[str, Any]) -> EconomicCollectDto:
        bc_idx: int = item["bc_idx"]
        title: str = item["title"]
        dept: str = item.get("dept") or ""
        date_str: str = item.get("date_str") or ""

        source_url = f"{_BASE_VIEW_URL}?cbIdx={_CB_IDX}&bcIdx={bc_idx}"
        pub_at = _parse_date(date_str)
        amount = parse_krw_amount(title)

        return EconomicCollectDto(
            source_type=_SOURCE_TYPE,
            source_url=source_url,
            raw_title=title[:500],
            investor_name=_INVESTOR_NAME,
            target_company_or_fund=None,
            investment_amount=amount,
            currency="KRW",
            raw_metadata={
                "bc_idx": bc_idx,
                "dept": dept,
                "date_raw": date_str,
                "data_role": "POLICY_SIGNAL",
                "industry_sector": "SME_STARTUP",
                "collected_via": "mss-bbs-scraper",
            },
            published_at=pub_at,
        )


__all__ = ["MssBbsCollector", "MssWatermark", "_parse_list_page", "_parse_date"]
