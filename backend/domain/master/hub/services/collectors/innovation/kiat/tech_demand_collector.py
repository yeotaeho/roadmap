# KIAT 기술은행 수요기술 조회 API에서 기업의 기술 수요(TECH_DEMAND_SIGNAL)를 수집한다

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

import aiohttp
import xmltodict

from domain.master.models.transfer.innovation_collect_dto import InnovationCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "INNOVATION_KIAT_TECH_DEMAND"
_DATA_ROLE = "TECH_DEMAND_SIGNAL"

# KIAT 기술은행 수요기술 조회 서비스_GW (data.go.kr/15158929). 표준 data.go.kr REST(XML, serviceKey).
#   2026-06-24 live 확인: resultCode 00, response.body.items.item.
_BASE_URL = "https://apis.data.go.kr/B552536/tech_1/needtech"
# 수요기술 상세 URL(소스 식별 — dmdtchNo 기반 안정 키, 멱등성용).
_NTB_NEED_BASE = "https://www.ntb.kr/techDemand/view.do?dmdtchNo="


def _ensure_list(value: Any) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def parse_needtech_items(xml_text: str) -> list[dict[str, Any]]:
    """needtech XML 응답에서 item 리스트 추출(표준 response.body.items.item)."""
    text = (xml_text or "").strip()
    if not text:
        return []
    try:
        data = xmltodict.parse(text)
    except Exception:
        logger.error("KIAT 수요기술 응답 파싱 실패: %s", text[:200])
        return []
    response = data.get("response") if isinstance(data, dict) else None
    if not isinstance(response, dict):
        return []
    body = response.get("body") if isinstance(response.get("body"), dict) else {}
    items_wrapper = body.get("items") if isinstance(body, dict) else None
    if isinstance(items_wrapper, dict):
        items = _ensure_list(items_wrapper.get("item"))
    elif isinstance(items_wrapper, list):
        items = items_wrapper
    else:
        items = []
    return [it for it in items if isinstance(it, dict)]


def _salvage_items(xml_text: str) -> list[dict[str, Any]]:
    """잘린(truncated) XML 응답에서 완전한 <item>…</item> 블록만 건져 파싱."""
    out: list[dict[str, Any]] = []
    for m in re.finditer(r"<item>.*?</item>", xml_text or "", re.DOTALL):
        try:
            parsed = xmltodict.parse(m.group(0))
            node = parsed.get("item") if isinstance(parsed, dict) else None
            if isinstance(node, dict):
                out.append(node)
        except Exception:
            continue
    return out


def _result_code(xml_text: str) -> str:
    try:
        data = xmltodict.parse(xml_text)
        return _clean(data.get("response", {}).get("header", {}).get("resultCode"))
    except Exception:
        return ""


def item_to_dto(item: dict[str, Any]) -> InnovationCollectDto | None:
    """수요기술 item → InnovationCollectDto (TECH_DEMAND_SIGNAL)."""
    title = _clean(item.get("dmdtchNm"))  # 수요기술명
    if not title:
        return None
    demand_no = _clean(item.get("dmdtchNo"))
    keyword = _clean(item.get("keyword")).strip(",")
    raw_metadata: dict[str, Any] = {
        "data_role": _DATA_ROLE,
        "demand_no": demand_no or None,
        "buy_kind": _clean(item.get("buyKindNm")) or None,  # 구매유형(기술매매/협력)
        "progress": _clean(item.get("dmdtchPrgstCd")) or None,  # 진행상태
        "hope_period": _clean(item.get("hopepcEraCd")) or None,  # 희망기간
        "transfer_purpose": _clean(item.get("tchlgyIndcprDtl")) or None,  # 이전목적
        "purchase_condition": _clean(item.get("tchlgyPccndCn")) or None,  # 구매조건
        "contract_type": _clean(item.get("tcntrnCntrctTy")) or None,
        "keyword": keyword or None,
    }
    return InnovationCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=f"{_NTB_NEED_BASE}{demand_no}" if demand_no else None,
        title=title[:500],
        author_or_assignee=(_clean(item.get("tchdlSpinsttNm")) or None),  # 전담기관
        abstract_text=(_clean(item.get("hopetchSumnsfeCn")) or None),  # 희망기술개요
        raw_metadata=raw_metadata,
        published_at=None,
    )


class KiatTechDemandCollector:
    """KIAT 기술은행 수요기술 — 기업이 등록한 '필요 기술' 수집(수요 신호)."""

    BASE_URL = _BASE_URL

    def __init__(self, service_key: str):
        if not service_key or not service_key.strip():
            raise ValueError("KIAT 수요기술 API 키가 비어 있습니다. TECH_DEMAND_SIGNAL 을 설정하세요.")
        self._key = service_key.strip()

    async def collect(
        self, *, max_items: int = 200, num_rows: int = 100
    ) -> tuple[list[InnovationCollectDto], dict[str, int]]:
        stats = {"requests_total": 0, "requests_ok": 0, "errors": 0, "fetched": 0}
        collected: list[InnovationCollectDto] = []
        seen: set[str] = set()
        page = 1
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            consecutive_empty = 0
            max_pages = max_items // min(num_rows, 100) + 5  # 런어웨이 방지 상한
            while len(collected) < max_items and page <= max_pages:
                params = {
                    "serviceKey": self._key,
                    "pageNo": str(page),
                    "numOfRows": str(min(num_rows, 100)),
                }
                items: list[dict] = []
                body_text = ""
                truncated = False
                end_of_data = False
                # 일시적 잘림/타임아웃 대비 페이지당 최대 2회 시도.
                for attempt in range(2):
                    stats["requests_total"] += 1
                    try:
                        async with session.get(self.BASE_URL, params=params) as resp:
                            resp.raise_for_status()
                            body_text = await resp.text()
                        if _result_code(body_text) not in ("00", "0", ""):
                            logger.warning("KIAT 수요기술 비정상 응답 page=%s", page)
                            end_of_data = True
                            break
                        items = parse_needtech_items(body_text)
                        if items or "<item>" not in body_text:
                            stats["requests_ok"] += 1
                            break
                        truncated = True  # <item> 있는데 0건 → 잘림
                    except Exception:
                        truncated = True
                        stats["errors"] += 1
                        logger.warning("[kiat-tech-demand] page=%s 시도 %s 실패", page, attempt + 1)
                    await asyncio.sleep(0.5)

                if end_of_data:
                    break
                # 결정적 잘림 페이지 → 완전한 item만 건져내고 다음 페이지로 진행(중단 X)
                if not items and truncated:
                    items = _salvage_items(body_text)
                    logger.warning(
                        "[kiat-tech-demand] page=%s 잘림 — %s건 건짐 후 다음 페이지", page, len(items)
                    )

                if not items:
                    consecutive_empty += 1
                    if consecutive_empty >= 3:
                        break  # 연속 빈 페이지 → 실제 끝
                    page += 1
                    continue
                consecutive_empty = 0

                for item in items:
                    dto = item_to_dto(item)
                    if dto is None:
                        continue
                    key = dto.source_url or dto.title
                    if key in seen:
                        continue
                    seen.add(key)
                    collected.append(dto)
                    if len(collected) >= max_items:
                        break
                # 잘리지 않은 정상 페이지가 numOfRows 미만 → 마지막 페이지
                if not truncated and len(items) < min(num_rows, 100):
                    break
                page += 1
        stats["fetched"] = len(collected)
        return collected, stats

    def collect_sync(self, *, max_items: int = 200) -> tuple[list[InnovationCollectDto], dict[str, int]]:
        return asyncio.run(self.collect(max_items=max_items))


__all__ = ["KiatTechDemandCollector", "parse_needtech_items", "item_to_dto"]
