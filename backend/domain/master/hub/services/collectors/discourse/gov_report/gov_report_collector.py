# 정부 부처 보도자료(정책브리핑 korea.kr) RSS 수집 — 정책 담론(DISCOURSE_GOV_REPORT)

from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import Any

import feedparser

from domain.master.hub.services.collectors.discourse.news_rss.news_rss_collector import (
    _html_to_text,
    _parse_published_at,
)
from domain.master.hub.services.collectors.economic.common.rss_wordpress_sync import (
    fetch_html_sync,
)
from domain.master.models.transfer.discourse_collect_dto import DiscourseCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "DISCOURSE_GOV_REPORT"
# 정책브리핑 통합 보도자료 RSS(부처 전체). description 에 전체 본문 포함.
_RSS_URL = "https://www.korea.kr/rss/pressrelease.xml"
# 제목 접두 "[외교부]제목..." 에서 부처명 분리.
_AGENCY_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)")


def parse_gov_rss(raw_feed: str | bytes, *, max_items: int = 50) -> list[DiscourseCollectDto]:
    """정책브리핑 보도자료 RSS → DiscourseCollectDto. 부처명은 제목 [부처] 접두에서 추출."""
    parsed = feedparser.parse(raw_feed)
    if getattr(parsed, "bozo", 0) and not parsed.entries:
        logger.warning("[gov-report] RSS 파싱 경고: %s", getattr(parsed, "bozo_exception", ""))
    out: list[DiscourseCollectDto] = []
    for entry in parsed.entries[:max_items]:
        raw_title = html.unescape((entry.get("title") or "").strip())
        link = (entry.get("link") or "").strip()
        if not raw_title or not link:
            continue
        m = _AGENCY_RE.match(raw_title)
        if m:
            agency, headline = m.group(1).strip(), m.group(2).strip()
        else:
            agency, headline = None, raw_title
        content_body = _html_to_text(entry.get("summary", "") or "", max_len=12000)
        raw_metadata: dict[str, Any] = {"agency": agency} if agency else {}
        if guid := entry.get("id", ""):
            raw_metadata["guid"] = guid
        out.append(
            DiscourseCollectDto(
                source_type=_SOURCE_TYPE,
                source_url=link,
                headline=(headline or raw_title)[:500],
                author_or_publisher=agency,
                content_body=content_body or None,
                raw_metadata=raw_metadata or None,
                published_at=_parse_published_at(entry),
            )
        )
    return out


class GovReportCollector:
    """정부 보도자료 담론 수집 — 정책브리핑(korea.kr) 통합 RSS."""

    RSS_URL = _RSS_URL

    async def collect(
        self, *, max_items: int = 50
    ) -> tuple[list[DiscourseCollectDto], dict[str, int]]:
        raw = await asyncio.to_thread(fetch_html_sync, self.RSS_URL, tag="gov-report")
        if not raw:
            logger.warning("[gov-report] RSS fetch 실패 url=%s", self.RSS_URL)
            return [], {"fetched": 0, "errors": 1}
        rows = parse_gov_rss(raw, max_items=max_items)
        logger.info("[gov-report] 정책브리핑 보도자료 수집 %s건", len(rows))
        return rows, {"fetched": len(rows), "errors": 0}


__all__ = ["GovReportCollector", "parse_gov_rss"]
