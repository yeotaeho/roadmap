# 온통청년 청년센터 OpenAPI 기반 Bronze 수집 (오프라인 지원기관 마스터)

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "OPP_YOUTH_CENTER"

# TODO: 실제 API 엔드포인트 확인 필요 — 온통청년 OpenAPI 승인 후 재검증
_BASE_URL = "https://www.youthcenter.go.kr/openApi/youth/center"  # TODO: 검증 필요


def _parse_item(item: dict) -> Optional[OpportunityCollectDto]:
    """온통청년 청년센터 API 응답 item → OpportunityCollectDto.

    TODO: API 승인 후 실제 응답 필드명으로 매핑 교체.
    아래 필드명은 온통청년 OpenAPI 문서 기준 추정값.
    """
    # TODO: 실제 센터명 필드명 확인 (예: cntrNm, centerName, name 등)
    raw_title = (
        item.get("cntrNm")
        or item.get("centerName")
        or item.get("name")
        or ""
    )
    raw_title = str(raw_title).strip()
    if not raw_title:
        return None

    # TODO: 실제 센터 ID 필드명 확인 (예: cntrNo, centerId, id 등)
    center_id = (
        item.get("cntrNo")
        or item.get("centerId")
        or item.get("id")
        or ""
    )
    center_id = str(center_id).strip()

    # TODO: source_url 패턴 검증 필요
    if center_id:
        source_url = f"https://www.youthcenter.go.kr/center/{center_id}"
    else:
        source_url = _BASE_URL

    # TODO: 실제 운영기관 필드명 확인 (예: operInstNm, operOrg, hostOrg 등)
    host_name = (
        item.get("operInstNm")
        or item.get("operOrg")
        or item.get("hostOrg")
        or "온통청년"
    )

    # TODO: 실제 센터 소개 필드명 확인 (예: cntrIntrCn, centerInfo, content 등)
    raw_content = (
        item.get("cntrIntrCn")
        or item.get("centerInfo")
        or item.get("content")
    )

    # 청년센터는 상설 운영이므로 published_at/deadline_at 이 없을 수 있음
    # TODO: 개소일·운영종료일 필드명 확인
    published_at: Optional[datetime] = None
    for field in ("openDt", "openDate", "estDt"):
        raw_date = item.get(field)
        if raw_date:
            try:
                published_at = datetime.fromisoformat(str(raw_date)).replace(
                    tzinfo=timezone.utc
                )
                break
            except Exception:
                pass

    raw_metadata: dict[str, Any] = {
        "center_id": center_id,
        # TODO: 실제 주소 필드명 확인 (예: rdnmadr, address, addr 등)
        "address": item.get("rdnmadr") or item.get("address") or item.get("addr"),
        # TODO: 실제 연락처 필드명 확인 (예: phoneNo, telNo, tel 등)
        "phone": item.get("phoneNo") or item.get("telNo") or item.get("tel"),
        # TODO: 실제 지역 필드명 확인 (예: ctprvnNm, region, siNm 등)
        "region": item.get("ctprvnNm") or item.get("region") or item.get("siNm"),
        "original_item": item,
    }

    return OpportunityCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=source_url,
        raw_title=raw_title[:500],
        host_name=str(host_name)[:150],
        raw_content=raw_content,
        raw_metadata=raw_metadata,
        published_at=published_at,
        deadline_at=None,
    )


class YouthCenterCollector:
    """온통청년 청년센터 OpenAPI Collector — 오프라인 지원기관 마스터 수집.

    TODO: 온통청년 OpenAPI 승인 후 아래 항목 재검증 필요.
      1. _BASE_URL — 실제 엔드포인트 확인
      2. 페이지네이션 파라미터명
      3. 응답 래퍼 구조
      4. _parse_item 내 모든 TODO 필드명
    """

    def __init__(self, service_key: str):
        if not service_key or not service_key.strip():
            raise ValueError(
                "온통청년 API 키가 비어 있습니다. YOUTH_POLICY_SERVICE_KEY 를 설정하세요."
            )
        self._service_key = service_key.strip()

    async def collect(self, *, max_items: int = 200) -> list[OpportunityCollectDto]:
        """온통청년 청년센터 API를 페이지 순회하며 OpportunityCollectDto 리스트 반환."""
        page_no = 1
        per_page = min(max_items, 100)
        collected: list[OpportunityCollectDto] = []
        seen: set[str] = set()
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            while len(collected) < max_items:
                # TODO: 실제 파라미터명·값 포맷 확인 후 교체
                params: dict[str, str] = {
                    "serviceKey": self._service_key,
                    "pageIndex": str(page_no),   # TODO: 파라미터명 검증
                    "numOfRows": str(per_page),   # TODO: 파라미터명 검증
                    "returnType": "json",          # TODO: 필요 여부 확인
                }
                try:
                    async with session.get(_BASE_URL, params=params) as resp:
                        if resp.status != 200:
                            raise RuntimeError(
                                f"온통청년 청년센터 API HTTP {resp.status} (page={page_no})"
                            )
                        data = await resp.json(content_type=None)
                except aiohttp.ClientError as e:
                    raise RuntimeError(f"온통청년 청년센터 API 네트워크 오류: {e}") from e

                # TODO: 실제 응답 래퍼 구조에 맞게 items 추출 경로 교체
                items: list[dict] = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    body = data.get("response", data)
                    if isinstance(body, dict):
                        body = body.get("body", body)
                    items_raw = body.get("items") if isinstance(body, dict) else None
                    if isinstance(items_raw, list):
                        items = items_raw
                    elif isinstance(items_raw, dict):
                        item = items_raw.get("item")
                        items = item if isinstance(item, list) else ([item] if item else [])
                    elif isinstance(data.get("data"), list):
                        items = data["data"]

                if not items:
                    break

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    try:
                        dto = _parse_item(item)
                    except Exception:
                        logger.warning("온통청년 청년센터 아이템 파싱 실패, 스킵")
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

        logger.info("온통청년 청년센터 수집 완료: %s건 (page=%s까지)", len(collected), page_no)
        return collected


__all__ = ["YouthCenterCollector"]
