# 창업진흥원 K-Startup 통합공고 OpenAPI 기반 Bronze 수집 (정부 창업지원 기회)

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

import aiohttp
import xmltodict
from bs4 import BeautifulSoup

from domain.master.hub.services.collectors.economic.common.rss_wordpress_sync import fetch_html_sync
from domain.master.hub.services.collectors.opportunity.smes_collector import (
    _ensure_list,
    _parse_date_to_kst,
)
from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "OPP_KSTARTUP_GRANT"

# K-Startup 지원사업 공고정보. data.go.kr 게이트웨이(serviceKey) 형태를 기본으로 한다.
#   대안 호스트: https://nidapi.k-startup.go.kr/api/kisedKstartupService/v1/getAnnouncementInformation
#   키/네트워크 확보 시 live 1회 호출로 호스트·필드명 재검증 필요(메모리 교훈).
_BASE_URL = (
    "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
)
_KSTARTUP_DETAIL = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?pbancSn="
_KSTARTUP_HOME = "https://www.k-startup.go.kr"

_TITLE_FIELDS = ("biz_pbanc_nm", "intg_pbanc_biz_nm", "bizPbancNm", "pbancNm", "title")
_CONTENT_FIELDS = ("pbanc_ctnt", "pbancCn", "bizPbancCn", "dataContents")
_HOST_FIELDS = ("sprv_inst", "biz_prch_dprt_nm", "sprvInst", "insttNm")
_START_FIELDS = ("pbanc_rcpt_bgng_dt", "pbancRcptBgngDt", "applicationStartDate")
_END_FIELDS = ("pbanc_rcpt_end_dt", "pbancRcptEndDt", "applicationEndDate")
_URL_FIELDS = ("detl_pg_url", "detlPgUrl", "pblancUrl", "url")
_ID_FIELDS = ("pbanc_sn", "pbancSn", "id")
_CLASSIFICATION_FIELDS = ("supt_biz_clsfc", "suptBizClsfc")
_TARGET_FIELDS = ("aply_trgt_ctnt", "aplyTrgtCtnt", "aply_trgt")

# API pbanc_ctnt 는 130자 요약만 제공 — 상세 페이지 fetch 로 보강
_ENRICH_THRESHOLD = 200

# K-Startup 상세 HTML 본문 컨테이너 셀렉터 (우선순위순)
_KSTARTUP_BODY_SELECTORS: tuple[str, ...] = (
    ".information_list",
    ".view_cont",
    ".pbanc_cont",
    "#cont_body",
)


def _pick(item: dict, fields: tuple[str, ...]) -> Optional[str]:
    for f in fields:
        value = item.get(f)
        if value is None:
            continue
        s = str(value).strip()
        if s:
            return s
    return None


def extract_items(body_text: str) -> list[dict]:
    """K-Startup 응답(JSON data[] 또는 data.go.kr XML wrapping)을 item 리스트로 정규화."""
    text = (body_text or "").strip()
    if not text:
        return []

    # 1) JSON 우선 (신형 — {"data":[...]} 또는 {"response":...})
    if text.startswith(("{", "[")):
        try:
            data = json.loads(text)
        except Exception:
            return []
        if isinstance(data, list):
            return [it for it in data if isinstance(it, dict)]
        if isinstance(data, dict):
            if isinstance(data.get("data"), list):
                return [it for it in data["data"] if isinstance(it, dict)]
            # response.body.items.item 폴백
            response = data.get("response", data)
            body = response.get("body", response) if isinstance(response, dict) else {}
            items_wrapper = body.get("items") if isinstance(body, dict) else None
            if isinstance(items_wrapper, dict):
                return [it for it in _ensure_list(items_wrapper.get("item")) if isinstance(it, dict)]
            if isinstance(items_wrapper, list):
                return [it for it in items_wrapper if isinstance(it, dict)]
        return []

    # 2) XML (data.go.kr 표준 wrapping)
    try:
        data = xmltodict.parse(text)
    except Exception:
        logger.error("K-Startup 응답 파싱 실패: %s", text[:200])
        return []
    response = data.get("response", data) if isinstance(data, dict) else {}
    if not isinstance(response, dict):
        return []
    body = response.get("body", response) if isinstance(response.get("body"), dict) else response
    items_wrapper = body.get("items") if isinstance(body, dict) else None
    if isinstance(items_wrapper, dict):
        items = _ensure_list(items_wrapper.get("item"))
    elif isinstance(items_wrapper, list):
        items = items_wrapper
    else:
        items = _ensure_list(body.get("item") if isinstance(body, dict) else None)
    return [it for it in items if isinstance(it, dict)]


def parse_item(item: dict) -> Optional[OpportunityCollectDto]:
    """K-Startup item → OpportunityCollectDto (4대 함정 방어)."""
    raw_title = _pick(item, _TITLE_FIELDS)
    if not raw_title:
        return None

    # 함정 4 — source_url 3단계 Fallback (NOT NULL 보장)
    url = _pick(item, _URL_FIELDS) or ""
    if not url.startswith("http"):
        pbanc_sn = _pick(item, _ID_FIELDS)
        url = f"{_KSTARTUP_DETAIL}{pbanc_sn}" if pbanc_sn else _KSTARTUP_HOME

    published_at = None
    for f in _START_FIELDS:
        published_at = _parse_date_to_kst(item.get(f))
        if published_at:
            break
    deadline_at = None
    for f in _END_FIELDS:
        deadline_at = _parse_date_to_kst(item.get(f))
        if deadline_at:
            break

    raw_metadata: dict[str, Any] = {
        "announcement_id": _pick(item, _ID_FIELDS),
        "classification": _pick(item, _CLASSIFICATION_FIELDS),
        "apply_target": _pick(item, _TARGET_FIELDS),
        "original_item": item,
    }

    return OpportunityCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=url,
        raw_title=raw_title[:500],
        host_name=(_pick(item, _HOST_FIELDS) or "창업진흥원")[:150],
        raw_content=_pick(item, _CONTENT_FIELDS),  # 함정 3 — 원형 보존
        raw_metadata=raw_metadata,
        published_at=published_at,
        deadline_at=deadline_at,
    )


def extract_kstartup_body(html: str, *, max_len: int = 4000) -> str:
    """K-Startup 공고 상세 HTML에서 본문 텍스트 추출. 셀렉터 미매칭 시 빈 문자열."""
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return ""
    for sel in _KSTARTUP_BODY_SELECTORS:
        node = soup.select_one(sel)
        if node is None:
            continue
        text = re.sub(r"\s+", " ", node.get_text(separator=" ", strip=True)).strip()
        if len(text) > 50:
            return text[:max_len]
    return ""


class KStartupCollector:
    """K-Startup 통합공고 OpenAPI Collector — 정부 창업지원 기회 수집."""

    BASE_URL = _BASE_URL

    def __init__(self, service_key: str):
        if not service_key or not service_key.strip():
            raise ValueError("K-Startup API 키가 비어 있습니다. KSTARTUP_SERVICE_KEY 를 설정하세요.")
        self._service_key = service_key.strip()

    async def collect(self, *, max_items: int = 100) -> list[OpportunityCollectDto]:
        page_no = 1
        per_page = min(max_items, 100)
        collected: list[OpportunityCollectDto] = []
        seen: set[str] = set()
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            while len(collected) < max_items:
                params = {
                    "serviceKey": self._service_key,
                    "page": str(page_no),
                    "perPage": str(per_page),
                    "returnType": "json",
                }
                try:
                    async with session.get(self.BASE_URL, params=params) as resp:
                        if resp.status != 200:
                            raise RuntimeError(f"K-Startup API HTTP {resp.status} (page={page_no})")
                        body_text = await resp.text()
                except aiohttp.ClientError as e:
                    raise RuntimeError(f"K-Startup API 네트워크 오류: {e}") from e

                items = extract_items(body_text)
                if not items:
                    break
                for item in items:
                    try:
                        dto = parse_item(item)
                    except Exception:
                        logger.warning("K-Startup 아이템 파싱 실패, 스킵")
                        continue
                    if dto is None or dto.source_url in seen:
                        continue
                    seen.add(dto.source_url)
                    collected.append(dto)
                    if len(collected) >= max_items:
                        break
                if len(items) < per_page:
                    break
                page_no += 1

        logger.info("K-Startup 수집 완료: %s건 (page=%s까지)", len(collected), page_no)

        # 본문 보강 — API 요약(130자)이 짧은 항목만 상세 페이지 fetch
        short = [dto for dto in collected if len(dto.raw_content or "") < _ENRICH_THRESHOLD]
        if short:
            sem = asyncio.Semaphore(5)

            async def _enrich(dto: OpportunityCollectDto) -> None:
                async with sem:
                    try:
                        html = await asyncio.to_thread(
                            fetch_html_sync, dto.source_url, tag="kstartup-body"
                        )
                        body = extract_kstartup_body(html)
                        if body and len(body) > len(dto.raw_content or ""):
                            dto.raw_content = body
                    except Exception:
                        logger.warning(
                            "K-Startup 본문 보강 실패 url=%s", dto.source_url, exc_info=False
                        )

            await asyncio.gather(*[_enrich(dto) for dto in short])
            enriched_count = sum(
                1 for dto in short if len(dto.raw_content or "") >= _ENRICH_THRESHOLD
            )
            logger.info("K-Startup 본문 보강 완료: %s/%s건", enriched_count, len(short))

        return collected

    def collect_sync(self, *, max_items: int = 100) -> list[OpportunityCollectDto]:
        return asyncio.run(self.collect(max_items=max_items))


__all__ = ["KStartupCollector", "extract_items", "parse_item", "extract_kstartup_body"]
