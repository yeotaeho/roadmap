# 조달청 나라장터 입찰공고 OpenAPI 수집 — 골격(정부→민간 자본 흐름 신호)

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import aiohttp
import xmltodict

_KST = timezone(timedelta(hours=9))

from domain.master.hub.services.collectors.opportunity.smes_collector import (
    _ensure_list,
    _parse_date_to_kst,
)
from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "OPP_G2B_BID"

# 나라장터 입찰공고정보(용역). 업무구분별 오퍼레이션이 분리되어 있으므로 차기 확장 시 물품·공사 추가.
#   문서: https://www.data.go.kr/data/15129394/openapi.do
#   키/네트워크 확보 시 live 1회 호출로 오퍼레이션·필드명 재검증 필요.
_BASE_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"
_G2B_HOME = "https://www.g2b.go.kr"

_TITLE_FIELDS = ("bidNtceNm",)
_HOST_FIELDS = ("ntceInsttNm", "dminsttNm")
_START_FIELDS = ("bidNtceDt",)
_END_FIELDS = ("bidClseDt", "opengDt")
_URL_FIELDS = ("bidNtceDtlUrl", "bidNtceUrl")
_ID_FIELDS = ("bidNtceNo",)


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
    """나라장터 응답(JSON/XML)을 item 리스트로 정규화."""
    text = (body_text or "").strip()
    if not text:
        return []
    if text.startswith(("{", "[")):
        try:
            data = json.loads(text)
        except Exception:
            return []
    else:
        try:
            data = xmltodict.parse(text)
        except Exception:
            logger.error("나라장터 응답 파싱 실패: %s", text[:200])
            return []
    if not isinstance(data, dict):
        return []
    response = data.get("response", data)
    body = response.get("body", response) if isinstance(response, dict) else {}
    items_wrapper = body.get("items") if isinstance(body, dict) else None
    if isinstance(items_wrapper, dict):
        items = _ensure_list(items_wrapper.get("item"))
    elif isinstance(items_wrapper, list):
        items = items_wrapper
    else:
        items = _ensure_list(body.get("item") if isinstance(body, dict) else None)
    return [it for it in items if isinstance(it, dict)]


def parse_item(item: dict) -> Optional[OpportunityCollectDto]:
    raw_title = _pick(item, _TITLE_FIELDS)
    if not raw_title:
        return None
    url = _pick(item, _URL_FIELDS) or ""
    if not url.startswith("http"):
        url = _G2B_HOME
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
        "bid_no": _pick(item, _ID_FIELDS),
        "budget_amount": item.get("asignBdgtAmt") or item.get("presmptPrce"),
        "demand_institution": item.get("dminsttNm"),
        "original_item": item,
    }
    return OpportunityCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=url,
        raw_title=raw_title[:500],
        host_name=(_pick(item, _HOST_FIELDS) or "조달청")[:150],
        raw_content=None,
        raw_metadata=raw_metadata,
        published_at=published_at,
        deadline_at=deadline_at,
    )


class NarajangteoCollector:
    """나라장터 입찰공고(용역) — 키 게이트 골격 수집기."""

    BASE_URL = _BASE_URL

    def __init__(self, service_key: str):
        if not service_key or not service_key.strip():
            raise ValueError("나라장터 API 키가 비어 있습니다. NARAJANGTEO_SERVICE_KEY 를 설정하세요.")
        self._service_key = service_key.strip()

    async def collect(
        self, *, max_items: int = 100, days_back: int = 30
    ) -> list[OpportunityCollectDto]:
        collected: list[OpportunityCollectDto] = []
        seen: set[str] = set()
        # 필수값(2026-06-24 live 확인): inqryDiv(조회구분=1 공고게시일시) + 조회기간(YYYYMMDDHHMM).
        now = datetime.now(tz=_KST)
        bgn = (now - timedelta(days=days_back)).strftime("%Y%m%d") + "0000"
        end = now.strftime("%Y%m%d") + "2359"
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            params = {
                "serviceKey": self._service_key,
                "pageNo": "1",
                "numOfRows": str(min(max_items, 100)),
                "type": "json",
                "inqryDiv": "1",
                "inqryBgnDt": bgn,
                "inqryEndDt": end,
            }
            try:
                async with session.get(self.BASE_URL, params=params) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"나라장터 API HTTP {resp.status}")
                    body_text = await resp.text()
            except aiohttp.ClientError as e:
                raise RuntimeError(f"나라장터 API 네트워크 오류: {e}") from e

            for item in extract_items(body_text):
                try:
                    dto = parse_item(item)
                except Exception:
                    continue
                if dto is None or dto.source_url in seen:
                    continue
                seen.add(dto.source_url)
                collected.append(dto)
                if len(collected) >= max_items:
                    break
        logger.info("나라장터 수집 완료: %s건", len(collected))
        return collected


__all__ = ["NarajangteoCollector", "extract_items", "parse_item"]
