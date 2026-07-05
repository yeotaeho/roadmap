# 코치 웹 tool 2종 — Tavily 검색·WaterCrawl 본문 추출(read-only, 출처 URL 필수 반환)

from __future__ import annotations

import asyncio
import ipaddress
import logging
from urllib.parse import urlparse

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

WEB_TOOL_LABELS: dict[str, str] = {
    "web_search": "웹 검색",
    "fetch_url": "웹 페이지 읽기",
}

_TAVILY_ENDPOINT = "https://api.tavily.com/search"
_SEARCH_MAX_RESULTS = 5
_SEARCH_TIMEOUT_S = 15.0
_SNIPPET_MAX_CHARS = 300
_FETCH_TIMEOUT_S = 45.0
_PAGE_MAX_CHARS = 8000


def shape_search_results(data: dict) -> dict:
    """Tavily 응답 → 축약 결과. 행마다 출처 url 을 보장한다(없는 행은 제외)."""
    results = []
    for r in data.get("results") or []:
        url = r.get("url")
        if not url:
            continue
        results.append(
            {
                "title": r.get("title") or "",
                "url": url,
                "snippet": (r.get("content") or "")[:_SNIPPET_MAX_CHARS],
            }
        )
        if len(results) >= _SEARCH_MAX_RESULTS:
            break
    return {"results": results}


def shape_page(url: str, result: dict) -> dict:
    """WaterCrawl scrape 응답 → 축약 본문. 중첩({"result": {...}})·평면 양쪽을 방어한다."""
    inner = result.get("result") if isinstance(result.get("result"), dict) else result
    markdown = (inner or {}).get("markdown") or ""
    truncated = len(markdown) > _PAGE_MAX_CHARS
    return {"url": url, "content": markdown[:_PAGE_MAX_CHARS], "truncated": truncated}


def is_fetchable_url(url: str) -> bool:
    """fetch_url 허용 검사 — http/https 공인 호스트만. 사설/루프백/비표준 스킴은 거부한다."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith((".local", ".internal")):
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass  # 도메인명은 통과 — 공인 웹 대상이 원칙이고 실제 fetch 는 WaterCrawl 클라우드가 수행한다.
    return True


def build_web_tools(settings=None) -> list:
    """키가 등록된 웹 tool 만 생성한다 — 미설정 tool 은 목록에서 제외(모델이 호출 시도조차 안 하게)."""
    if settings is None:
        from core.config.settings import get_settings

        settings = get_settings()

    tools: list = []
    tavily_key = getattr(settings, "tavily_api_key", None)
    watercrawl_key = getattr(settings, "watercrawl_api_key", None)

    if tavily_key:

        @tool
        async def web_search(query: str) -> dict:
            """내부 데이터로 답할 수 없는 최신 정보(뉴스·시세·마감 임박 공고·기술 동향)를 웹에서 검색한다. 결과의 출처 URL 을 답변에 반드시 표기한다."""
            try:
                # httpx AsyncClient 는 요청마다 생성 — 루프 바인딩 회피(웹 호출은 저빈도).
                async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT_S) as client:
                    res = await client.post(
                        _TAVILY_ENDPOINT,
                        headers={"Authorization": f"Bearer {tavily_key}"},
                        json={"query": query, "max_results": _SEARCH_MAX_RESULTS},
                    )
                if res.status_code != 200:
                    logger.warning(f"Tavily 검색 실패(status {res.status_code})")
                    return {"error": f"웹 검색에 실패했습니다(status {res.status_code})."}
                return shape_search_results(res.json())
            except Exception as e:  # 웹 실패는 대화를 끊지 않는다 — 관찰로 되돌린다.
                logger.warning(f"Tavily 검색 예외: {e}")
                return {"error": "웹 검색 중 오류가 발생했습니다."}

        tools.append(web_search)
    else:
        logger.warning("TAVILY_API_KEY 미설정 — web_search tool 비활성.")

    if watercrawl_key:

        @tool
        async def fetch_url(url: str) -> dict:
            """웹 검색으로 찾은 특정 페이지의 본문을 읽는다(공고 원문·기사 전문 확인용)."""

            if not is_fetchable_url(url):
                return {"error": "지원하지 않는 URL 입니다(http/https 공인 주소만 가능)."}

            def _scrape() -> dict:
                # watercrawl-py 는 동기(requests) 클라이언트 — 스레드에서 생성·호출해 루프를 막지 않는다.
                from watercrawl import WaterCrawlAPIClient

                return WaterCrawlAPIClient(watercrawl_key).scrape_url(url)

            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(_scrape), timeout=_FETCH_TIMEOUT_S
                )
                return shape_page(url, result or {})
            except asyncio.TimeoutError:
                return {"error": "페이지 로드가 시간 초과되었습니다."}
            except Exception as e:  # 웹 실패는 대화를 끊지 않는다 — 관찰로 되돌린다.
                logger.warning(f"WaterCrawl 추출 예외: {e}")
                return {"error": "페이지 본문을 가져오지 못했습니다."}

        tools.append(fetch_url)
    else:
        logger.warning("WATERCRAWL_API_KEY 미설정 — fetch_url tool 비활성.")

    return tools
