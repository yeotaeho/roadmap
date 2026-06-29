# 온통청년 청년정책 OpenAPI 기반 Bronze 수집 (정부 청년정책·지원사업)

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "OPP_YOUTH_POLICY"

# TODO: 실제 API 엔드포인트 확인 필요 — 온통청년 OpenAPI 승인 후 재검증
# 온통청년 포털: https://www.youthcenter.go.kr
# 현재 URL은 추정값이며, 공공데이터포털(data.go.kr) 게이트웨이 또는 자체 도메인 중 하나일 수 있음
_BASE_URL = "https://www.youthcenter.go.kr/openApi/youth/policy"  # TODO: 검증 필요


def _parse_item(item: dict) -> Optional[OpportunityCollectDto]:
    """온통청년 청년정책 API 응답 item → OpportunityCollectDto.

    TODO: API 승인 후 실제 응답 필드명으로 매핑 교체.
    아래 필드명은 온통청년 OpenAPI 문서 기준 추정값.
    """
    # TODO: 실제 제목 필드명 확인 (예: plcyNm, policyName, title 등)
    raw_title = (
        item.get("plcyNm")
        or item.get("policyName")
        or item.get("title")
        or ""
    )
    raw_title = str(raw_title).strip()
    if not raw_title:
        return None

    # TODO: 실제 정책 ID 필드명 확인 (예: plcyNo, policyId, id 등)
    policy_id = (
        item.get("plcyNo")
        or item.get("policyId")
        or item.get("id")
        or ""
    )
    policy_id = str(policy_id).strip()

    # TODO: source_url 패턴 검증 필요 — 온통청년 정책 상세 URL 구조
    if policy_id:
        source_url = f"https://www.youthcenter.go.kr/youngPlcy/youngPlcyUnif/{policy_id}"
    else:
        source_url = _BASE_URL

    # TODO: 실제 기관명 필드명 확인 (예: sprvInstNm, hostOrg, institNm 등)
    host_name = (
        item.get("sprvInstNm")
        or item.get("hostOrg")
        or item.get("institNm")
        or "온통청년"
    )

    # TODO: 실제 본문 필드명 확인 (예: plcyCn, policyCont, content 등)
    raw_content = (
        item.get("plcyCn")
        or item.get("policyCont")
        or item.get("content")
    )

    # TODO: 실제 날짜 필드명·포맷 확인 (예: aplySttDt, applyStartDate, startDate 등)
    published_at: Optional[datetime] = None
    for field in ("aplySttDt", "applyStartDate", "startDate", "rgsttDt"):
        raw_date = item.get(field)
        if raw_date:
            try:
                published_at = datetime.fromisoformat(str(raw_date)).replace(
                    tzinfo=timezone.utc
                )
                break
            except Exception:
                pass

    # TODO: 실제 마감일 필드명 확인 (예: aplyEndDt, applyEndDate, endDate 등)
    deadline_at: Optional[datetime] = None
    for field in ("aplyEndDt", "applyEndDate", "endDate", "deadlineDate"):
        raw_date = item.get(field)
        if raw_date:
            try:
                deadline_at = datetime.fromisoformat(str(raw_date)).replace(
                    tzinfo=timezone.utc
                )
                break
            except Exception:
                pass

    raw_metadata: dict[str, Any] = {
        "policy_id": policy_id,
        # TODO: 실제 정책 분류 필드명 확인 (예: plcyClsfNm, policyType 등)
        "policy_type": item.get("plcyClsfNm") or item.get("policyType"),
        # TODO: 실제 지원 대상 필드명 확인 (예: aplyTrgtNm, targetGroup 등)
        "target_group": item.get("aplyTrgtNm") or item.get("targetGroup"),
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
        deadline_at=deadline_at,
    )


class YouthPolicyCollector:
    """온통청년 청년정책 OpenAPI Collector — 일자리·주거·교육·복지 정책 수집.

    TODO: 온통청년 OpenAPI 승인 후 아래 항목 재검증 필요.
      1. _BASE_URL — 실제 엔드포인트 확인
      2. 페이지네이션 파라미터명 (pageIndex, pageNo, page 등)
      3. 응답 래퍼 구조 (response.body.items 또는 data[] 등)
      4. _parse_item 내 모든 TODO 필드명
    """

    def __init__(self, service_key: str):
        if not service_key or not service_key.strip():
            raise ValueError(
                "온통청년 API 키가 비어 있습니다. YOUTH_POLICY_SERVICE_KEY 를 설정하세요."
            )
        self._service_key = service_key.strip()

    async def collect(self, *, max_items: int = 200) -> list[OpportunityCollectDto]:
        """온통청년 청년정책 API를 페이지 순회하며 OpportunityCollectDto 리스트 반환."""
        # TODO: 실제 페이지 파라미터명 확인 (pageIndex / pageNo / page 등)
        page_no = 1
        # TODO: 실제 페이지당 건수 파라미터명 확인 (numOfRows / perPage / size 등)
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
                                f"온통청년 청년정책 API HTTP {resp.status} (page={page_no})"
                            )
                        data = await resp.json(content_type=None)
                except aiohttp.ClientError as e:
                    raise RuntimeError(f"온통청년 청년정책 API 네트워크 오류: {e}") from e

                # TODO: 실제 응답 래퍼 구조에 맞게 items 추출 경로 교체
                # 예상 구조: {"response": {"body": {"items": [...]}}} 또는 {"data": [...]}
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
                        logger.warning("온통청년 청년정책 아이템 파싱 실패, 스킵")
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

        logger.info("온통청년 청년정책 수집 완료: %s건 (page=%s까지)", len(collected), page_no)
        return collected


__all__ = ["YouthPolicyCollector"]
