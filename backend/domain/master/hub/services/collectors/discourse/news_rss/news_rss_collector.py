# 국내 뉴스 RSS에서 담론(이슈·리스크) 헤드라인을 수집한다

from __future__ import annotations

import asyncio
import calendar
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
from bs4 import BeautifulSoup

from domain.master.hub.services.collectors.economic.common.rss_wordpress_sync import (
    fetch_html_sync,
)
from domain.master.models.transfer.discourse_collect_dto import DiscourseCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "DISCOURSE_NEWS_RSS"


@dataclass(frozen=True)
class NewsFeed:
    publisher: str
    category: str
    url: str


# 2026-06 live 검증 완료 피드. URL이 죽으면 수집기는 해당 피드만 스킵(메모리 교훈).
# discourse 축은 LLM 섹터 분류라 피드별 섹터 매핑 불필요 — category 는 메타로만 남긴다.
_FEEDS: tuple[NewsFeed, ...] = (
    NewsFeed("한국경제", "economy", "https://www.hankyung.com/feed/economy"),
    NewsFeed("전자신문", "tech", "https://rss.etnews.com/Section901.xml"),
    NewsFeed("전자신문", "breaking", "https://rss.etnews.com/Section902.xml"),
    NewsFeed("ZDNet Korea", "it", "https://feeds.feedburner.com/zdkorea"),
    # 2026-06-28 미달 섹터 활성화(Phase 2) — 토픽 전문지 피드 11종 live 검증 후 추가.
    # 사회서비스(시장축 없는 마지막 회색 섹터)에 복지 전문지 3종을 집중 공급한다.
    NewsFeed("웰페어뉴스", "welfare", "https://www.welfarenews.net/rss/allArticle.xml"),
    NewsFeed("복지타임즈", "welfare", "https://www.bokjitimes.com/rss/allArticle.xml"),
    NewsFeed("정책브리핑", "welfare", "https://www.korea.kr/rss/dept_mw.xml"),
    NewsFeed("전자신문", "finance", "http://rss.etnews.com/02027.xml"),
    NewsFeed("한국경제", "finance", "https://www.hankyung.com/feed/finance"),
    NewsFeed("금융위원회", "finance", "http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111"),
    NewsFeed("전자신문", "content", "http://rss.etnews.com/03104.xml"),
    NewsFeed("모터그래프", "mobility", "https://www.motorgraph.com/rss/allArticle.xml"),
    NewsFeed("에듀플러스", "edutech", "https://www.eduplusnews.com/rss/allArticle.xml"),
    NewsFeed("물류신문", "logistics", "https://www.klnews.co.kr/rss/allArticle.xml"),
    NewsFeed("뷰티경제", "beauty", "https://www.thebk.co.kr/rss/allArticle.xml"),
)


def _parse_published_at(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            # feedparser 의 *_parsed 는 UTC struct_time 이므로 timegm(UTC) 로 변환.
            ts = calendar.timegm(parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, TypeError, OverflowError):
            pass
    for key in ("published", "updated"):
        pub_str = entry.get(key, "")
        if pub_str:
            try:
                dt = parsedate_to_datetime(pub_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError, OverflowError):
                continue
    return None


def _html_to_text(html: str, *, max_len: int = 4000) -> str:
    if not html:
        return ""
    try:
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    except Exception:
        text = html
    return re.sub(r"\s+", " ", text).strip()[:max_len]


# RSS 본문이 이 길이 미만이면 원문 페이지에서 본문을 보강한다.
_ENRICH_THRESHOLD = 280

# 기사 본문 컨테이너 셀렉터 — schema.org 표준(itemprop) 우선, 매체 공통 클래스 폴백.
_BODY_SELECTORS: tuple[str, ...] = (
    "[itemprop=articleBody]",
    "div.article-body",
    ".article-body",
    "#articletxt",
    "#article-view-content-div",
    "article",
)


def extract_article_body(html: str, *, max_len: int = 4000) -> str:
    """뉴스 원문 HTML에서 본문 텍스트만 추출(네비·푸터 노이즈 제외). 실패 시 빈 문자열."""
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return ""
    for sel in _BODY_SELECTORS:
        node = soup.select_one(sel)
        if node is None:
            continue
        text = re.sub(r"\s+", " ", node.get_text(separator=" ", strip=True)).strip()
        if text:
            return text[:max_len]
    return ""


def parse_feed_entries(
    raw_feed: str | bytes,
    feed: NewsFeed,
    *,
    max_items: int = 50,
    fetch_article: Callable[[str], str] | None = None,
) -> list[DiscourseCollectDto]:
    """feedparser 입력(문자열/바이트/URL)을 DiscourseCollectDto 리스트로 변환.

    fetch_article 주입 시 RSS 본문이 짧으면(``_ENRICH_THRESHOLD`` 미만) 원문에서 보강한다.
    """
    parsed = feedparser.parse(raw_feed)
    if getattr(parsed, "bozo", 0) and not parsed.entries:
        logger.warning(
            "[news-rss] 피드 파싱 경고 publisher=%s: %s",
            feed.publisher,
            getattr(parsed, "bozo_exception", ""),
        )
    out: list[DiscourseCollectDto] = []
    for entry in parsed.entries[:max_items]:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        summary = entry.get("summary", "") or ""
        content_body = _html_to_text(summary)
        if fetch_article is not None and len(content_body) < _ENRICH_THRESHOLD:
            try:
                fetched = fetch_article(link)
            except Exception:
                logger.warning("[news-rss] 본문 보강 실패 url=%s", link, exc_info=False)
                fetched = ""
            if fetched and len(fetched) > len(content_body):
                content_body = fetched[:4000]
        tags = [t.get("term") for t in entry.get("tags", []) if t.get("term")]
        raw_metadata: dict[str, object] = {
            "category": feed.category,
            "publisher": feed.publisher,
        }
        if guid := entry.get("id", ""):
            raw_metadata["guid"] = guid
        if tags:
            raw_metadata["tags"] = tags
        out.append(
            DiscourseCollectDto(
                source_type=_SOURCE_TYPE,
                source_url=link,
                headline=title[:500],
                author_or_publisher=feed.publisher,
                content_body=content_body or None,
                raw_metadata=raw_metadata,
                published_at=_parse_published_at(entry),
            )
        )
    return out


def _fetch_article_body(url: str) -> str:
    """원문 페이지를 받아 본문 텍스트만 추출(news_rss 본문 보강용)."""
    return extract_article_body(fetch_html_sync(url, tag="news-rss-body"))


class NewsRssCollector:
    """국내 뉴스 RSS 멀티 피드 — 카테고리(경제·산업·IT) 헤드라인 수집."""

    def collect_sync(
        self, *, max_items_per_feed: int = 50
    ) -> tuple[list[DiscourseCollectDto], dict[str, int]]:
        stats = {"feeds_total": len(_FEEDS), "feeds_ok": 0, "errors": 0, "fetched": 0}
        out: list[DiscourseCollectDto] = []
        for feed in _FEEDS:
            try:
                # feedparser 의 자체 fetch 대신 브라우저 UA httpx 로 받아 넘긴다.
                # (UA 차단·인코딩 차이로 feedparser URL fetch 가 빈 결과/bozo 되는 매체 방어)
                raw = fetch_html_sync(feed.url, tag="news-rss")
                if not raw:
                    stats["errors"] += 1
                    logger.warning("[news-rss] 피드 fetch 실패 publisher=%s", feed.publisher)
                    continue
                rows = parse_feed_entries(
                    raw,
                    feed,
                    max_items=max_items_per_feed,
                    fetch_article=_fetch_article_body,
                )
                out.extend(rows)
                stats["feeds_ok"] += 1
            except Exception:
                stats["errors"] += 1
                logger.exception("[news-rss] 피드 수집 실패 publisher=%s", feed.publisher)
        stats["fetched"] = len(out)
        logger.info("뉴스 RSS 수집 완료: %s건 (피드 %s/%s)", len(out), stats["feeds_ok"], len(_FEEDS))
        return out, stats

    async def collect(
        self, *, max_items_per_feed: int = 50
    ) -> tuple[list[DiscourseCollectDto], dict[str, int]]:
        return await asyncio.to_thread(
            lambda: self.collect_sync(max_items_per_feed=max_items_per_feed)
        )


__all__ = ["NewsRssCollector", "NewsFeed", "parse_feed_entries", "extract_article_body"]
