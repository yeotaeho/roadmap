"""스타트업레시피 RSS 기반 경제 Bronze 수집.

설계 메모 (2026-05-11 RSS probe 기반):
  - RSS URL : https://startuprecipe.co.kr/feed
  - 포맷    : WordPress 표준 RSS 2.0 (`content:encoded` 풀텍스트 제공)
  - 빈도    : 일 2~10건 (정부/스타트업 보도자료 기반)
  - 특이사항:
      1) 대부분의 글이 ``[AI서머리] 헤드라인1‧헤드라인2`` 형태의 **묶음(digest)** 글이며,
         1개 본문에 5~10개 별개 사건(투자/IPO/펀드 결성 + 단순 행사·정책)이 섞여 있다.
      2) RSS `tags` 가 거의 모두 ``['news']`` 로 시그널이 없으므로,
         **Wowtale 처럼 태그 기반 필터링이 불가능**하다.
      3) 그래서 본 컬렉터는:
         - 묶음글(`[AI서머리]` prefix)은 **무조건 통과**시키고
           ``STARTUPRECIPE_DIGEST`` 라는 별도 source_type 으로 적재한다.
           (개별 사건 분해는 Silver/LLM 단계의 책임으로 위임)
         - 일반 글(단일 사건 기사)은 **제목 + 본문 키워드 매칭**으로 노이즈 필터링.

운영 보완 (Wowtale 컬렉터와 동일 정책):
  - feedparser ``published_parsed`` (UTC struct_time) → KST(UTC+9) 변환
  - ``content:encoded`` 우선 사용 (없으면 ``summary`` fallback) + 출처 기록
  - 노이즈 필터 통과 건수와 스킵 건수 모두 반환 (관측성)
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

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)


_KST = timezone(timedelta(hours=9))

# 스타트업레시피의 묶음(digest) 글 prefix 모음.
# `[AI서머리]` 외에도 `[이번주행사]`, `[이번주이벤트]`, `[채용]`, `[금주의 펀딩]` 등이 자주 등장한다.
# 이 prefix들이 붙은 글은 1개 본문에 여러 사건이 섞여 있어 개별 사건 분류가 의미없으므로
# 모두 ``STARTUPRECIPE_DIGEST`` 로 일관 처리한다.
_DIGEST_PREFIX_RE = re.compile(
    r"^\s*\[\s*(?:"
    r"AI\s*서머리"
    r"|이번주[\s ]?(?:행사|이벤트|펀딩|투자)"
    r"|금주(?:의)?[\s ]?(?:펀딩|투자|행사)"
    r"|이벤트"
    r"|행사"
    r"|채용"
    r")\s*\]",
    re.IGNORECASE,
)

# 제목 맨 앞에 붙는 일반적인 ``[…]`` 태그를 제거하기 위한 패턴 (investor_name 추출용).
_BRACKET_PREFIX_RE = re.compile(r"^\s*\[[^\]]{0,30}\]\s*")

# 일반(단일 사건) 글에 대해서만 적용되는 1차 노이즈 필터.
# 묶음글에는 이 검사를 건너뛴다 (`_is_relevant` 참고).
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
    "투자유치",
    "조달",
    "투자받",
    "베팅",
    "벤처투자",
    "벤처캐피탈",
    "Funding",
    "funding",
)

# 제목 매칭 우선순위 — 구체적인 키워드부터.
# Wowtale 와 분류 체계는 통일하되 prefix 만 ``STARTUPRECIPE_`` 로 둔다.
_SOURCE_TYPE_RULES: tuple[tuple[str, str], ...] = (
    ("M&A", "STARTUPRECIPE_MA"),
    ("인수합병", "STARTUPRECIPE_MA"),
    ("인수", "STARTUPRECIPE_MA"),
    ("합병", "STARTUPRECIPE_MA"),
    ("Pre-IPO", "STARTUPRECIPE_IPO"),
    ("프리IPO", "STARTUPRECIPE_IPO"),
    ("IPO", "STARTUPRECIPE_IPO"),
    ("상장", "STARTUPRECIPE_IPO"),
    ("펀드 결성", "STARTUPRECIPE_FUND"),
    ("펀드결성", "STARTUPRECIPE_FUND"),
    ("결성", "STARTUPRECIPE_FUND"),
    ("펀드", "STARTUPRECIPE_FUND"),
)
_DIGEST_SOURCE_TYPE = "STARTUPRECIPE_DIGEST"
_DEFAULT_SOURCE_TYPE = "STARTUPRECIPE_INVEST"


def _is_digest_title(title: str) -> bool:
    return bool(_DIGEST_PREFIX_RE.search(title))


def _classify_source_type(title: str, tags: list[str], *, is_digest: bool) -> str:
    if is_digest:
        return _DIGEST_SOURCE_TYPE
    haystack = title + " " + " ".join(tags)
    for keyword, stype in _SOURCE_TYPE_RULES:
        if keyword in haystack:
            return stype
    return _DEFAULT_SOURCE_TYPE


def _is_relevant(
    title: str, tags: list[str], full_text: str, *, is_digest: bool
) -> bool:
    """노이즈 필터.

    - 묶음글(``[AI서머리]``)은 거의 항상 일부 투자 사건을 포함하므로 무조건 통과.
    - 일반 글은 제목 + 본문에서 투자 키워드를 1개 이상 발견해야 통과.
    """
    if is_digest:
        return True
    haystack_short = title + " " + " ".join(tags)
    if any(k in haystack_short for k in _INVESTMENT_KEYWORDS):
        return True
    # 제목이 너무 일반적이면 본문 앞부분에서 한 번 더 확인 (LLM 비용 절감용 보강)
    body_head = full_text[:2000]
    return any(k in body_head for k in _INVESTMENT_KEYWORDS)


def _parse_published_at(entry: dict) -> datetime | None:
    """RSS pubDate를 KST 타임존이 붙은 datetime 으로 변환."""
    parsed = entry.get("published_parsed")
    if parsed:
        try:
            ts = time.mktime(parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(_KST)
        except (ValueError, TypeError, OverflowError):
            logger.warning("StartupRecipe published_parsed 변환 실패: %s", parsed)

    pub_str = entry.get("published", "")
    if pub_str:
        try:
            dt = parsedate_to_datetime(pub_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(_KST)
        except (ValueError, TypeError, OverflowError):
            logger.warning("StartupRecipe published 문자열 파싱 실패: %s", pub_str)

    return None


def _extract_html_content(entry: dict) -> str:
    """기사 전문(`content:encoded`)을 우선, 없으면 요약본을 사용."""
    content_list = entry.get("content") or []
    if content_list:
        try:
            first = content_list[0]
            value = (
                first.get("value")
                if isinstance(first, dict)
                else getattr(first, "value", "")
            )
            if value:
                return str(value)
        except (AttributeError, IndexError, TypeError):
            pass
    return entry.get("summary", "") or ""


def _html_to_text(html: str, *, max_len: int = 8000) -> str:
    """묶음글의 본문이 4~10KB 수준으로 길어 Wowtale(5KB) 보다 한도를 키웠다."""
    if not html:
        return ""
    try:
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    except Exception:
        text = html
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


class StartupRecipeEconomicCollector:
    """스타트업레시피 투자/스타트업 뉴스 RSS 수집기.

    - RSS URL: https://startuprecipe.co.kr/feed
    - 표준 RSS 2.0 (WordPress)
    - 업데이트: 일 2~10건
    - 특이사항: ``[AI서머리]`` digest 글이 다수
    """

    RSS_URL = "https://startuprecipe.co.kr/feed"

    def collect_sync(
        self, *, max_items: int = 50
    ) -> tuple[list[EconomicCollectDto], int]:
        """RSS 피드 동기 수집.

        Returns:
            (수집된 DTO 리스트, 노이즈 필터로 스킵된 건수)
        """
        try:
            feed = feedparser.parse(self.RSS_URL)
        except Exception:
            logger.exception("StartupRecipe RSS 파싱 실패")
            raise

        if feed.bozo:
            logger.warning(
                "StartupRecipe RSS 파싱 경고: %s", feed.bozo_exception
            )

        out: list[EconomicCollectDto] = []
        skipped = 0
        for entry in feed.entries[:max_items]:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue

            tags = [
                t.term for t in entry.get("tags", []) if getattr(t, "term", None)
            ]

            html_content = _extract_html_content(entry)
            full_text = _html_to_text(html_content)

            is_digest = _is_digest_title(title)

            if not _is_relevant(title, tags, full_text, is_digest=is_digest):
                skipped += 1
                continue

            published_at = _parse_published_at(entry)
            source_type = _classify_source_type(title, tags, is_digest=is_digest)

            # 묶음글은 제목 첫 토큰이 회사명이 아닐 확률이 높으므로 investor_name 추출을 생략한다.
            investor_name = (
                None if is_digest else self._extract_investor_from_title(title)
            )

            raw_metadata: dict[str, object] = {}
            if guid := entry.get("id", ""):
                raw_metadata["guid"] = guid
            if tags:
                raw_metadata["tags"] = tags
            if is_digest:
                raw_metadata["is_digest"] = True
            if full_text:
                raw_metadata["content_text"] = full_text
                raw_metadata["content_source"] = (
                    "content_encoded" if entry.get("content") else "summary"
                )
            elif summary := entry.get("summary", ""):
                raw_metadata["summary"] = summary[:2000]

            out.append(
                EconomicCollectDto(
                    source_type=source_type,
                    source_url=link,
                    raw_title=title[:500],
                    investor_name=investor_name,
                    target_company_or_fund=None,
                    investment_amount=None,
                    raw_metadata=raw_metadata or None,
                    published_at=published_at,
                )
            )

        logger.info(
            "StartupRecipe RSS 수집 완료: %s건 (노이즈 스킵 %s건)",
            len(out),
            skipped,
        )
        return out, skipped

    async def collect(
        self, *, max_items: int = 50
    ) -> tuple[list[EconomicCollectDto], int]:
        return await asyncio.to_thread(
            lambda: self.collect_sync(max_items=max_items)
        )

    def _extract_investor_from_title(self, title: str) -> str | None:
        """단일 사건 기사 전용. 제목 첫 토큰을 임시 투자사명으로 사용.

        - 선행 ``[…]`` 카테고리 태그(있다면)는 회사명이 아니므로 제거 후 추출한다.
        - Phase 3 에서 본문 + LLM 으로 정확도 향상 예정.
        """
        stripped = _BRACKET_PREFIX_RE.sub("", title).strip()
        if not stripped:
            return None
        match = re.match(r"^([^,·‧]+)", stripped)
        if not match:
            return None
        candidate = match.group(1).strip()
        if not candidate or len(candidate) >= 50:
            return None
        return candidate[:255] or None
