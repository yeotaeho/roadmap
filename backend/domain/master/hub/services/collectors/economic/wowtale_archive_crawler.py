"""Wowtale 카테고리 아카이브 페이지 기반 과거 기사 크롤링 (Backfill 전용).

RSS는 최근 50건만 제공한다. 1년치 이상 과거 데이터가 필요할 때
카테고리 아카이브 페이지(/category/{slug}/page/{n}/)를 순회해 수집한다.

기본 대상 카테고리:
    funding          → raw_economic_data  (투자 유치)
    venture-capital  → raw_economic_data  (VC 동향)
    Global-news      → raw_economic_data  (해외 투자, 필터 적용)

설계 원칙:
    - 동기 HTTP(httpx.Client) + asyncio.to_thread  → 기존 rss_wordpress_sync 패턴 통일
    - 1초 sleep (페이지 간), 0.5초 (기사 상세 간)  → 서버 부하 방지
    - source_url UNIQUE 제약 기반 중복 제거 → Repository 단 ON CONFLICT DO NOTHING
    - from_date 컷오프: URL 경로의 날짜(/YYYY/MM/DD/)로 조기 중단 판단
"""

from __future__ import annotations

import asyncio
import logging
import re
import time as _time_module
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, Sequence

import httpx
from bs4 import BeautifulSoup

from domain.master.hub.services.collectors.economic._rss_investment_krw import (
    extract_investment_amount_krw,
)
from domain.master.hub.services.collectors.economic.rss_wordpress_sync import (
    wordpress_main_text,
)
from domain.master.hub.services.collectors.economic.wowtale_collector import (
    _classify_source_type,
    _is_investment_relevant,
)
from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

_KST: Final = timezone(timedelta(hours=9))
_BASE_URL: Final = "https://wowtale.net"

# 카테고리 slug → source_type 고정값 (None 이면 제목 기반 자동 분류)
_CATEGORY_SOURCE_TYPE: dict[str, str | None] = {
    "funding": None,            # 제목 기반: WOWTALE_MA / IPO / FUND / INVEST
    "venture-capital": "WOWTALE_VC",
    "Global-news": None,        # 제목 기반 + 투자 필터 적용
    "ai": "WOWTALE_AI",
    "bio-healthcare": "WOWTALE_BIO",
    "contests": "WOWTALE_CONTEST",
    "landscape": "WOWTALE_LANDSCAPE",
    "policy": "WOWTALE_POLICY",
}

_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://wowtale.net/",
}


# ---------------------------------------------------------------------------
# 내부 데이터 클래스
# ---------------------------------------------------------------------------


@dataclass
class _ArticleRef:
    """카테고리 아카이브 페이지에서 추출한 기사 기본 정보."""

    title: str
    url: str
    published_at: datetime | None  # URL 경로에서 추출 (fallback)
    category_slug: str


# ---------------------------------------------------------------------------
# 유틸리티 함수
# ---------------------------------------------------------------------------


def _parse_date_from_url(url: str) -> datetime | None:
    """URL 경로 /YYYY/MM/DD/ 에서 날짜를 추출해 KST 09:00 datetime 반환."""
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if not m:
        return None
    try:
        return datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            9, 0, 0, tzinfo=_KST,
        )
    except ValueError:
        return None


def _fetch_html(url: str, *, timeout: float = 25.0) -> str:
    """동기 HTTP GET. 실패 시 빈 문자열 반환."""
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception:
        logger.warning("Wowtale archive fetch 실패: %s", url, exc_info=False)
        return ""


def _parse_archive_page(
    html: str,
    category_slug: str,
) -> tuple[list[_ArticleRef], bool]:
    """카테고리 아카이브 페이지 HTML → (기사 ref 목록, 다음 페이지 존재 여부).

    CSS 셀렉터 우선순위 (WordPress 표준 → 커스텀 폴백):
        1) article.post h2.entry-title a
        2) article[class*='type-post'] h2 a
        3) article h2 a
    """
    if not html:
        return [], False

    soup = BeautifulSoup(html, "html.parser")

    articles = (
        soup.select("article.post")
        or soup.select("article[class*='type-post']")
        or soup.select("article")
    )

    refs: list[_ArticleRef] = []
    for art in articles:
        title_a = (
            art.select_one("h2.entry-title a")
            or art.select_one("h2 a")
            or art.select_one(".entry-title a")
        )
        if not title_a:
            continue

        title = title_a.get_text(strip=True)
        url = (title_a.get("href") or "").strip()
        if not title or not url or not url.startswith("http"):
            continue

        refs.append(
            _ArticleRef(
                title=title,
                url=url,
                published_at=_parse_date_from_url(url),
                category_slug=category_slug,
            )
        )

    has_next = soup.select_one("a.next.page-numbers") is not None
    return refs, has_next


def _parse_article_page(html: str) -> tuple[datetime | None, str]:
    """기사 상세 페이지 HTML → (정확한 published_at, 본문 텍스트).

    published_at 우선순위:
        1) <time class="entry-date" datetime="ISO8601">
        2) <time class="published" datetime="ISO8601">
        3) <time datetime="ISO8601">  (단순 폴백)
        4) None → 호출측에서 URL 날짜로 대체
    """
    if not html:
        return None, ""

    soup = BeautifulSoup(html, "html.parser")

    published_at: datetime | None = None
    for sel in (
        "time.entry-date[datetime]",
        "time.published[datetime]",
        "time[datetime]",
    ):
        tag = soup.select_one(sel)
        if not tag:
            continue
        dt_str = tag.get("datetime", "")
        if not dt_str:
            continue
        try:
            dt = datetime.fromisoformat(str(dt_str))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_KST)
            published_at = dt
            break
        except ValueError:
            pass

    body_text = wordpress_main_text(html, max_len=12000)
    return published_at, body_text


def _extract_investor_from_title(title: str) -> str | None:
    """제목에서 투자사 간단 추출 (wowtale_collector 의 인스턴스 메서드와 동일 로직)."""
    m = re.match(r"^([^,·]+)", title)
    if not m:
        return None
    candidate = m.group(1).strip()
    if not candidate or len(candidate) >= 50:
        return None
    return candidate[:255]


# ---------------------------------------------------------------------------
# 크롤러 클래스
# ---------------------------------------------------------------------------


class WowtaleArchiveCrawler:
    """Wowtale 카테고리 아카이브 페이지를 순회하는 Backfill 전용 크롤러.

    RSS 수집기(WowtaleEconomicCollector)가 최근 50건만 제공하는 한계를 보완한다.
    각 카테고리 아카이브 페이지를 순서대로 GET하며 기사 URL을 수집하고,
    선택적으로 기사 상세 페이지를 방문해 본문·정확한 날짜를 추출한다.

    사용 예::

        crawler = WowtaleArchiveCrawler()
        dtos = await crawler.crawl_all(max_pages=50, from_date=one_year_ago)
    """

    # (카테고리 slug, 투자 노이즈 필터 적용 여부)
    DEFAULT_CATEGORIES: tuple[tuple[str, bool], ...] = (
        ("funding", False),          # 투자 카테고리 자체 → 필터 불필요
        ("venture-capital", False),  # VC 카테고리 자체 → 필터 불필요
        ("Global-news", True),       # 해외 뉴스 → 투자 관련만 필터링
    )

    def __init__(
        self,
        *,
        sleep_sec: float = 1.0,
        article_sleep_sec: float = 0.5,
        fetch_article_body: bool = True,
        request_timeout: float = 25.0,
    ) -> None:
        self._sleep_sec = sleep_sec
        self._article_sleep_sec = article_sleep_sec
        self._fetch_article_body = fetch_article_body
        self._timeout = request_timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def crawl_category(
        self,
        category_slug: str,
        *,
        max_pages: int = 50,
        from_date: datetime | None = None,
        apply_investment_filter: bool = False,
        known_urls: set[str] | None = None,
    ) -> list[EconomicCollectDto]:
        """단일 카테고리 아카이브 전체 순회.

        Args:
            category_slug: 'funding', 'venture-capital' 등 WordPress 카테고리 slug.
            max_pages: 최대 순회 페이지 수 (페이지당 약 20건).
            from_date: 이 날짜 이전 기사는 수집 중단. None이면 max_pages까지 순회.
            apply_investment_filter: True면 _is_investment_relevant 필터 적용.
            known_urls: 이미 DB에 있는 URL 집합. 포함된 URL은 상세 크롤링 스킵.

        Returns:
            수집된 EconomicCollectDto 리스트.
        """
        return await asyncio.to_thread(
            self._crawl_category_sync,
            category_slug,
            max_pages=max_pages,
            from_date=from_date,
            apply_investment_filter=apply_investment_filter,
            known_urls=set(known_urls or set()),
        )

    async def crawl_all(
        self,
        *,
        categories: Sequence[tuple[str, bool]] | None = None,
        max_pages: int = 50,
        from_date: datetime | None = None,
        known_urls: set[str] | None = None,
    ) -> list[EconomicCollectDto]:
        """기본(또는 지정) 카테고리를 순차적으로 순회.

        카테고리 간에는 sleep_sec * 2 를 추가로 대기한다.
        """
        targets = list(categories or self.DEFAULT_CATEGORIES)
        all_dtos: list[EconomicCollectDto] = []
        seen: set[str] = set(known_urls or set())

        for slug, apply_filter in targets:
            logger.info("Wowtale archive: 카테고리 '%s' 시작", slug)
            try:
                dtos = await self.crawl_category(
                    slug,
                    max_pages=max_pages,
                    from_date=from_date,
                    apply_investment_filter=apply_filter,
                    known_urls=seen,
                )
            except Exception:
                logger.exception("Wowtale archive: 카테고리 '%s' 실패 → 스킵", slug)
                dtos = []

            # 다음 카테고리에서 동일 URL 재크롤링 방지
            seen.update(d.source_url for d in dtos if d.source_url)
            all_dtos.extend(dtos)
            logger.info("Wowtale archive: 카테고리 '%s' 완료 → %s건", slug, len(dtos))

            await asyncio.sleep(self._sleep_sec * 2)

        logger.info("Wowtale archive: 전체 완료 → 총 %s건", len(all_dtos))
        return all_dtos

    # ------------------------------------------------------------------
    # 내부 동기 구현 (asyncio.to_thread 로 실행)
    # ------------------------------------------------------------------

    def _crawl_category_sync(
        self,
        category_slug: str,
        *,
        max_pages: int,
        from_date: datetime | None,
        apply_investment_filter: bool,
        known_urls: set[str],
    ) -> list[EconomicCollectDto]:
        source_type_override = _CATEGORY_SOURCE_TYPE.get(category_slug)
        out: list[EconomicCollectDto] = []
        stop_crawl = False

        for page_num in range(1, max_pages + 1):
            if stop_crawl:
                break

            page_url = (
                f"{_BASE_URL}/category/{category_slug}/"
                if page_num == 1
                else f"{_BASE_URL}/category/{category_slug}/page/{page_num}/"
            )

            logger.debug("Wowtale archive: %s p%s GET", category_slug, page_num)
            html = _fetch_html(page_url, timeout=self._timeout)
            if not html:
                logger.warning("Wowtale archive: %s p%s 빈 응답 → 중단", category_slug, page_num)
                break

            refs, has_next = _parse_archive_page(html, category_slug)
            if not refs:
                logger.info("Wowtale archive: %s p%s 기사 없음 → 중단", category_slug, page_num)
                break

            for ref in refs:
                # from_date 컷오프: URL 날짜 기준 (느슨한 조건)
                if from_date and ref.published_at and ref.published_at < from_date:
                    logger.info(
                        "Wowtale archive: %s p%s from_date(%s) 도달 → 중단",
                        category_slug,
                        page_num,
                        from_date.date(),
                    )
                    stop_crawl = True
                    break

                # 투자 관련 필터 (Global-news 등 복합 카테고리용)
                if apply_investment_filter and not _is_investment_relevant(ref.title, []):
                    continue

                # 이미 알고 있는 URL: 상세 크롤링 스킵, DTO는 title+날짜만으로 생성
                already_known = ref.url in known_urls

                dto = self._build_dto(
                    ref,
                    source_type_override=source_type_override,
                    skip_article_fetch=already_known or not self._fetch_article_body,
                )
                if dto:
                    out.append(dto)
                    known_urls.add(ref.url)

                # 상세 페이지를 실제로 GET한 경우에만 sleep
                if not already_known and self._fetch_article_body:
                    _time_module.sleep(self._article_sleep_sec)

            if not has_next:
                logger.info("Wowtale archive: %s p%s 마지막 페이지", category_slug, page_num)
                break

            _time_module.sleep(self._sleep_sec)

        logger.info("Wowtale archive: %s 수집 완료 → %s건", category_slug, len(out))
        return out

    def _build_dto(
        self,
        ref: _ArticleRef,
        *,
        source_type_override: str | None,
        skip_article_fetch: bool,
    ) -> EconomicCollectDto | None:
        """단일 기사 ref → EconomicCollectDto 변환.

        skip_article_fetch=True 이면 제목·URL 날짜만으로 DTO 구성 (빠른 모드).
        skip_article_fetch=False 이면 기사 상세 페이지를 추가 GET해 본문과 정확한 날짜 추출.
        """
        published_at = ref.published_at
        body_text = ""
        content_source = "archive_url_date"

        if not skip_article_fetch:
            article_html = _fetch_html(ref.url, timeout=self._timeout)
            if article_html:
                precise_date, body_text = _parse_article_page(article_html)
                if precise_date:
                    published_at = precise_date
                content_source = "article_page" if body_text else "article_page_empty"

        # 투자 금액: 제목 + 본문 합쳐서 추출 (큰 값 우선)
        haystack = f"{ref.title}\n{body_text}"
        investment_amount = extract_investment_amount_krw(haystack)

        # source_type: 카테고리 고정값 또는 제목 기반 자동 분류
        source_type = source_type_override or _classify_source_type(ref.title, [])

        # 투자자: 제목 첫 토큰 (Phase 1 임시 규칙)
        investor_name = _extract_investor_from_title(ref.title)

        raw_metadata: dict[str, object] = {
            "category_slug": ref.category_slug,
            "content_source": content_source,
        }
        if body_text:
            raw_metadata["content_text"] = body_text[:8000]
        if investment_amount is not None:
            raw_metadata["investment_amount_krw_extracted"] = investment_amount
            raw_metadata["investment_amount_extraction"] = "regex_korean_units"

        return EconomicCollectDto(
            source_type=source_type,
            source_url=ref.url,
            raw_title=ref.title[:500],
            investor_name=investor_name,
            target_company_or_fund=None,
            investment_amount=investment_amount,
            raw_metadata=raw_metadata,
            published_at=published_at,
        )
