"""Wowtale RSS 기반 경제 Bronze 수집.

운영 보완 (2026-05-11):
  - 투자/자본 키워드 노이즈 필터 (Silver LLM 토큰 절감)
  - content:encoded 우선 사용 (없으면 summary fallback)
  - feedparser published_parsed(UTC struct_time) → KST(UTC+9) 변환
  - source_type 세분화: WOWTALE_MA / WOWTALE_IPO / WOWTALE_FUND / WOWTALE_INVEST
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

# 투자/자본 흐름과 무관한 RSS 아이템(인터뷰·행사·정책 일반)을 사전 차단해
# Silver(LLM) 단계의 불필요한 토큰 비용을 줄인다.
# 매칭 대상: 제목 + RSS 카테고리(tags) — Wowtale 은 카테고리에 강한 시그널이 들어있다.
_INVESTMENT_KEYWORDS: tuple[str, ...] = (
    # 자본 흐름 (제목 빈출)
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
    # 카테고리(tags) 강한 시그널 — Wowtale 카테고리 사례 반영
    "벤처캐피탈",
    "Venture Capital",
    "VC",
    "벤처투자",
    "Investments",
    "Investment",
)

# 제목 매칭 우선순위 — 더 구체적인(긴) 키워드부터 검사한다.
_SOURCE_TYPE_RULES: tuple[tuple[str, str], ...] = (
    ("M&A", "WOWTALE_MA"),
    ("인수합병", "WOWTALE_MA"),
    ("인수", "WOWTALE_MA"),
    ("합병", "WOWTALE_MA"),
    ("Pre-IPO", "WOWTALE_IPO"),
    ("프리IPO", "WOWTALE_IPO"),
    ("IPO", "WOWTALE_IPO"),
    ("상장", "WOWTALE_IPO"),
    ("펀드 결성", "WOWTALE_FUND"),
    ("펀드결성", "WOWTALE_FUND"),
    ("결성", "WOWTALE_FUND"),
    ("펀드", "WOWTALE_FUND"),
)
_DEFAULT_SOURCE_TYPE = "WOWTALE_INVEST"


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
    """RSS pubDate를 KST 타임존 정보가 붙은 datetime 으로 변환.

    우선순위:
      1) `published_parsed` (UTC struct_time) → KST 변환 (가장 안전)
      2) `published` (RFC 2822 문자열) → parsedate_to_datetime
    """
    parsed = entry.get("published_parsed")
    if parsed:
        try:
            ts = time.mktime(parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(_KST)
        except (ValueError, TypeError, OverflowError):
            logger.warning("Wowtale published_parsed 변환 실패: %s", parsed)

    pub_str = entry.get("published", "")
    if pub_str:
        try:
            dt = parsedate_to_datetime(pub_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(_KST)
        except (ValueError, TypeError, OverflowError):
            logger.warning("Wowtale published 문자열 파싱 실패: %s", pub_str)

    return None


def _extract_html_content(entry: dict) -> str:
    """기사 전문(`content:encoded`)을 우선, 없으면 요약본을 사용."""
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


_MIN_CHARS_PAGE_FETCH = 280


def _html_to_text(html: str, *, max_len: int = 5000) -> str:
    if not html:
        return ""
    try:
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    except Exception:
        text = html
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


class WowtaleEconomicCollector:
    """Wowtale 스타트업 투자 뉴스 RSS 피드 수집.

    - RSS URL: https://wowtale.net/feed/
    - 표준 RSS 2.0 (WordPress)
    - 업데이트: 실시간 (하루 3~10건)
    """

    RSS_URL = "https://wowtale.net/feed/"

    def collect_sync(
        self,
        *,
        max_items: int = 50,
        fetch_article_if_short: bool = True,
    ) -> tuple[list[EconomicCollectDto], int]:
        """RSS 피드 동기 수집.

        Args:
            max_items: RSS 상위 N개 엔트리.
            fetch_article_if_short: 본문(텍스트)이 짧으면 permalink GET 으로 보완.

        Returns:
            (수집된 DTO 리스트, 노이즈 필터로 스킵된 건수)
        """
        try:
            feed = feedparser.parse(self.RSS_URL)
        except Exception:
            logger.exception("Wowtale RSS 파싱 실패")
            raise

        if feed.bozo:
            logger.warning("Wowtale RSS 파싱 경고: %s", feed.bozo_exception)

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
                page_html = fetch_html_sync(link, tag="wowtale")
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
            "Wowtale RSS 수집 완료: %s건 (노이즈 스킵 %s건)", len(out), skipped
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
        """제목에서 투자사 이름 간단 추출 (Phase 1 임시 규칙).

        예:
            - "카카오벤처스, AI 스타트업에 투자" → "카카오벤처스"
            - "A벤처스·B캐피탈, C사 공동 투자" → "A벤처스"

        Phase 3에서 본문 크롤링 + LLM 으로 정확도 향상 예정.
        """
        match = re.match(r"^([^,·]+)", title)
        if not match:
            return None
        candidate = match.group(1).strip()
        if len(candidate) >= 50:
            return None
        return candidate[:255] or None
