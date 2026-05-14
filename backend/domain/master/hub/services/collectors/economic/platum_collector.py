"""Platum RSS 기반 경제 Bronze 수집 (투자·펀딩 카테고리).

Wowtale 과 동일한 정책:
  - 투자/자본 키워드 필터
  - ``content:encoded`` 우선, 짧으면 permalink WordPress 본문 fetch
  - ``_rss_investment_krw`` 로 원화 금액 추출
  - source_type: ``PLATUM_*`` 네임스페이스
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
from bs4 import BeautifulSoup

from domain.master.hub.services.collectors.economic._rss_investment_krw import (
    extract_investment_amount_krw,
)
from domain.master.hub.services.collectors.economic.rss_wordpress_sync import (
    fetch_html_sync,
    wordpress_main_text,
)
from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))

_INVESTMENT_KEYWORDS: tuple[str, ...] = (
    "투자",
    "유치",
    "라운드",
    "시리즈",
    "시드",
    "프리A",
    "Pre-A",
    "Pre-IPO",
    "프리IPO",
    "펀드",
    "결성",
    "인수",
    "합병",
    "M&A",
    "상장",
    "IPO",
    "Funding",
    "funding",
    "투자유치",
    "조달",
    "베팅",
    "벤처캐피탈",
    "Venture Capital",
    "VC",
    "벤처투자",
    "Investments",
    "Investment",
    "스타트업",
)

_SOURCE_TYPE_RULES: tuple[tuple[str, str], ...] = (
    ("M&A", "PLATUM_MA"),
    ("인수합병", "PLATUM_MA"),
    ("인수", "PLATUM_MA"),
    ("합병", "PLATUM_MA"),
    ("Pre-IPO", "PLATUM_IPO"),
    ("프리IPO", "PLATUM_IPO"),
    ("IPO", "PLATUM_IPO"),
    ("상장", "PLATUM_IPO"),
    ("펀드 결성", "PLATUM_FUND"),
    ("펀드결성", "PLATUM_FUND"),
    ("결성", "PLATUM_FUND"),
    ("펀드", "PLATUM_FUND"),
)
_DEFAULT_SOURCE_TYPE = "PLATUM_INVEST"

_MIN_CHARS_PAGE_FETCH = 280


def _classify_source_type(title: str, tags: list[str]) -> str:
    haystack = title + " " + " ".join(tags)
    for keyword, stype in _SOURCE_TYPE_RULES:
        if keyword in haystack:
            return stype
    return _DEFAULT_SOURCE_TYPE


def _is_investment_relevant(title: str, tags: list[str]) -> bool:
    haystack = title + " " + " ".join(tags)
    return any(keyword in haystack for keyword in _INVESTMENT_KEYWORDS)


def _parse_published_at(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed")
    if parsed:
        try:
            ts = time.mktime(parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(_KST)
        except (ValueError, TypeError, OverflowError):
            logger.warning("Platum published_parsed 변환 실패: %s", parsed)

    pub_str = entry.get("published", "")
    if pub_str:
        try:
            dt = parsedate_to_datetime(pub_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(_KST)
        except (ValueError, TypeError, OverflowError):
            logger.warning("Platum published 문자열 파싱 실패: %s", pub_str)

    return None


def _extract_html_content(entry: dict) -> str:
    content_list = entry.get("content") or []
    if content_list:
        try:
            first = content_list[0]
            value = first.get("value") if isinstance(first, dict) else getattr(first, "value", "")
            if value:
                return str(value)
        except (AttributeError, IndexError, TypeError):
            pass
    return entry.get("summary", "") or ""


def _html_to_text(html: str, *, max_len: int = 8000) -> str:
    if not html:
        return ""
    try:
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    except Exception:
        text = html
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


class PlatumEconomicCollector:
    """Platum 투자·펀딩 RSS.

    기본 피드: 펀딩 카테고리 (전체 메인 피드는 비투자 기사 비중이 높음).
    """

    RSS_URL = "https://platum.kr/archives/category/funding/feed"

    def collect_sync(
        self,
        *,
        max_items: int = 50,
        fetch_article_if_short: bool = True,
    ) -> tuple[list[EconomicCollectDto], int]:
        try:
            feed = feedparser.parse(self.RSS_URL)
        except Exception:
            logger.exception("Platum RSS 파싱 실패")
            raise

        if feed.bozo:
            logger.warning("Platum RSS 파싱 경고: %s", feed.bozo_exception)

        out: list[EconomicCollectDto] = []
        skipped = 0
        for entry in feed.entries[:max_items]:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue

            tags = [t.term for t in entry.get("tags", []) if getattr(t, "term", None)]

            if not _is_investment_relevant(title, tags):
                skipped += 1
                continue

            published_at = _parse_published_at(entry)

            html_content = _extract_html_content(entry)
            full_text = _html_to_text(html_content, max_len=8000)
            content_source = "content_encoded" if entry.get("content") else "summary"

            if fetch_article_if_short and len(full_text) < _MIN_CHARS_PAGE_FETCH:
                page_html = fetch_html_sync(link, tag="platum")
                page_text = wordpress_main_text(page_html)
                if len(page_text) > len(full_text):
                    full_text = page_text[:12000]
                    content_source = "permalink_html"

            haystack = f"{title}\n{full_text}"
            investment_amount = extract_investment_amount_krw(haystack)

            source_type = _classify_source_type(title, tags)
            investor_name = self._extract_investor_from_title(title)

            raw_metadata: dict[str, object] = {}
            if guid := entry.get("id", ""):
                raw_metadata["guid"] = guid
            if tags:
                raw_metadata["tags"] = tags
            if full_text:
                raw_metadata["content_text"] = full_text
                raw_metadata["content_source"] = content_source
            elif summary := entry.get("summary", ""):
                raw_metadata["summary"] = summary[:2000]
            if investment_amount is not None:
                raw_metadata["investment_amount_krw_extracted"] = investment_amount
                raw_metadata["investment_amount_extraction"] = "regex_korean_units"

            out.append(
                EconomicCollectDto(
                    source_type=source_type,
                    source_url=link,
                    raw_title=title[:500],
                    investor_name=investor_name,
                    target_company_or_fund=None,
                    investment_amount=investment_amount,
                    raw_metadata=raw_metadata or None,
                    published_at=published_at,
                )
            )

        logger.info(
            "Platum RSS 수집 완료: %s건 (노이즈 스킵 %s건)", len(out), skipped
        )
        return out, skipped

    async def collect(
        self,
        *,
        max_items: int = 50,
        fetch_article_if_short: bool = True,
    ) -> tuple[list[EconomicCollectDto], int]:
        return await asyncio.to_thread(
            lambda: self.collect_sync(
                max_items=max_items,
                fetch_article_if_short=fetch_article_if_short,
            )
        )

    def _extract_investor_from_title(self, title: str) -> str | None:
        match = re.match(r"^([^,·]+)", title)
        if not match:
            return None
        candidate = match.group(1).strip()
        if len(candidate) >= 50:
            return None
        return candidate[:255] or None


__all__ = ["PlatumEconomicCollector"]
