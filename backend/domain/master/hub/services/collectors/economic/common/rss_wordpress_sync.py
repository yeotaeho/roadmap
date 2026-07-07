"""WordPress 기반 RSS 사이트 permalink 동기 GET + 본문 텍스트 추출."""

from __future__ import annotations

import logging
import re
from typing import Final

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# RSS 피드 fetch 에도 재사용하는 공개 UA — feedparser 기본 UA 는 platum/venturesquare/wowtale 서 403/410 차단됨.
DEFAULT_RSS_UA: Final[str] = (
    "Mozilla/5.0 (compatible; RoadmapBronze/1.0) "
    "AppleWebKit/537.36 (KHTML, like Gecko)"
)
_DEFAULT_UA: Final[str] = DEFAULT_RSS_UA


def fetch_html_sync(url: str, *, timeout: float = 20.0, tag: str = "rss") -> str:
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": _DEFAULT_UA,
                "Accept-Language": "ko-KR,ko;q=0.9",
            },
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception:
        logger.warning("[%s] article fetch failed url=%s", tag, url, exc_info=False)
        return ""


def wordpress_main_text(html: str, *, max_len: int = 12000) -> str:
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for sel in (
            "article .entry-content",
            "div.entry-content",
            "article.post",
            "main article",
            "div.post-content",
        ):
            node = soup.select_one(sel)
            if node:
                t = node.get_text(separator=" ", strip=True)
                if len(t) > 80:
                    return re.sub(r"\s+", " ", t).strip()[:max_len]
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()[:max_len]
    except Exception:
        return ""
