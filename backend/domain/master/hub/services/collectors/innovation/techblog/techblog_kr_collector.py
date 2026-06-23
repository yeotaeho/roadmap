"""국내 주요 테크 기업 기술 블로그 RSS로 한국 기술 트렌드 신호를 수집한다."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
from bs4 import BeautifulSoup

from domain.master.models.transfer.innovation_collect_dto import InnovationCollectDto

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))
_SOURCE_TYPE = "INNOVATION_TECHBLOG_KR"

# (blog_name, rss_url, sector_hint)
_TECH_FEEDS: list[tuple[str, str, str]] = [
    ("naver_d2",     "https://d2.naver.com/d2.atom",                  "AI_INFRA"),
    ("kakao_tech",   "https://tech.kakao.com/feed",                   "AI_DATA"),
    ("line_eng",     "https://engineering.linecorp.com/ko/feed",      "BACKEND_INFRA"),
    ("woowahan",     "https://techblog.woowahan.com/feed",            "BACKEND_LOGISTICS"),
    ("toss",         "https://toss.tech/rss.xml",                     "FINTECH_MOBILE"),
    ("hyperconnect", "https://hyperconnect.github.io/feed.xml",       "AI_VIDEO"),
]

# 제목+요약 키워드로 기술 카테고리 분류 (앞쪽 규칙이 우선)
_TECH_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("AI_ML",    ("AI", "ML", "딥러닝", "머신러닝", "LLM", "ChatGPT", "GPT", "생성형", "추론", "임베딩")),
    ("DATA",     ("데이터", "Data", "Kafka", "Spark", "Flink", "ETL", "파이프라인", "분산처리", "배치")),
    ("INFRA",    ("인프라", "Kubernetes", "k8s", "AWS", "GCP", "Azure", "클라우드", "MSA", "마이크로서비스")),
    ("BACKEND",  ("백엔드", "API", "Spring", "FastAPI", "Django", "gRPC", "서버", "Node.js")),
    ("FRONTEND", ("프론트엔드", "React", "Vue", "Next.js", "웹", "TypeScript")),
    ("MOBILE",   ("Android", "iOS", "Flutter", "모바일", "앱")),
    ("DEVOPS",   ("DevOps", "CI/CD", "Jenkins", "GitHub Actions", "배포", "SRE", "모니터링")),
    ("SECURITY", ("보안", "Security", "인증", "OAuth", "JWT", "취약점", "암호화")),
    ("FINTECH",  ("결제", "금융", "핀테크", "Payment", "거래", "토스페이")),
)
_DEFAULT_CATEGORY = "TECH_GENERAL"


def _classify_tech_category(title: str, summary: str) -> str:
    haystack = f"{title} {summary}"
    for category, keywords in _TECH_CATEGORY_RULES:
        if any(kw in haystack for kw in keywords):
            return category
    return _DEFAULT_CATEGORY


def _parse_published_at(entry: Any) -> datetime | None:
    # RSS는 published, Atom은 updated만 갖는 경우가 많아 둘 다 폴백한다.
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            ts = time.mktime(parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(_KST)
        except (ValueError, TypeError, OverflowError):
            pass
    pub_str = entry.get("published", "") or entry.get("updated", "")
    if pub_str:
        try:
            dt = parsedate_to_datetime(pub_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(_KST)
        except (ValueError, TypeError, OverflowError):
            pass
    return None


def _extract_summary(entry: Any, *, max_len: int = 1500) -> str:
    # content:encoded 우선 → summary fallback
    content_list = entry.get("content") or []
    html = ""
    if content_list:
        try:
            first = content_list[0]
            html = (first.get("value") if isinstance(first, dict) else getattr(first, "value", "")) or ""
        except (AttributeError, IndexError, TypeError):
            pass
    if not html:
        html = entry.get("summary", "") or ""
    if not html:
        return ""
    try:
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    except Exception:
        text = html
    return re.sub(r"\s+", " ", text).strip()[:max_len]


def _collect_feed_sync(
    blog_name: str,
    rss_url: str,
    sector_hint: str,
    max_items: int,
) -> list[InnovationCollectDto]:
    try:
        feed = feedparser.parse(rss_url)
    except Exception:
        logger.exception("[techblog] RSS 파싱 실패: blog=%s url=%s", blog_name, rss_url)
        return []

    if feed.bozo:
        logger.warning("[techblog] RSS 파싱 경고: blog=%s %s", blog_name, feed.bozo_exception)

    rows: list[InnovationCollectDto] = []
    for entry in feed.entries[:max_items]:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue

        summary = _extract_summary(entry)
        category = _classify_tech_category(title, summary)
        published_at = _parse_published_at(entry)
        tags = [t.term for t in entry.get("tags", []) if getattr(t, "term", None)]

        rows.append(
            InnovationCollectDto(
                source_type=_SOURCE_TYPE,
                source_url=link,
                title=title[:500],
                author_or_assignee=None,
                abstract_text=summary or None,
                raw_metadata={
                    "blog_name": blog_name,
                    "sector_hint": sector_hint,
                    "tech_category": category,
                    "tags": tags,
                    "data_role": "TECH_BLOG_SIGNAL",
                },
                published_at=published_at,
            )
        )

    logger.debug("[techblog] blog=%s 수집 %d건", blog_name, len(rows))
    return rows


class TechBlogKrCollector:
    """국내 테크 기업 기술 블로그 RSS 수집기.

    source_url(permalink)이 UNIQUE 제약 키이므로 ON CONFLICT DO NOTHING으로 중복을 자동 처리한다.
    """

    def __init__(
        self,
        feeds: list[tuple[str, str, str]] | None = None,
    ) -> None:
        self._feeds = feeds or _TECH_FEEDS

    async def collect(
        self,
        *,
        max_items_per_feed: int = 30,
        sleep_seconds: float = 0.5,
    ) -> tuple[list[InnovationCollectDto], dict[str, int]]:
        stats: dict[str, int] = {
            "feeds_total": len(self._feeds),
            "feeds_ok": 0,
            "errors": 0,
            "fetched": 0,
        }
        all_rows: list[InnovationCollectDto] = []

        for i, (blog_name, rss_url, sector_hint) in enumerate(self._feeds):
            try:
                rows = await asyncio.to_thread(
                    _collect_feed_sync, blog_name, rss_url, sector_hint, max_items_per_feed
                )
                all_rows.extend(rows)
                stats["feeds_ok"] += 1
            except Exception:
                stats["errors"] += 1
                logger.exception("[techblog] 피드 수집 실패: blog=%s", blog_name)

            if i < len(self._feeds) - 1 and sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)

        stats["fetched"] = len(all_rows)
        logger.info("[techblog] 수집 완료 %d건 (피드 %d개)", len(all_rows), stats["feeds_ok"])
        return all_rows, stats


__all__ = [
    "TechBlogKrCollector",
    "_TECH_FEEDS",
    "_SOURCE_TYPE",
]
