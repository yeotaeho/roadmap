"""보조금24(gov24) 서비스 목록 컬렉터 — 정부→민간 자금 지원 선행 신호.

전략 (ECONOMIC_FLOW_IMPLEMENTATION_ROADMAP.md §4.4):
  - API: api.odcloud.kr/api/gov24/v3/serviceList
  - source_url: 상세조회URL (서비스ID 기반 고정 URL → 멱등 키)
  - 증분: cond[수정일시:GTE] 파라미터 → 수정·신규 서비스만 수집
  - 금액: `지원내용` 텍스트에서 KRW 정규식 파싱 (실패 시 None → Silver 레이어 LLM 보완)
  - source_type: GOVT_SUBSIDY24
  - 산업 관련 분야(창업·경영, 고용·노동 등) 전체 수집 후 Silver 레이어에서 필터링
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.odcloud.kr/api/gov24/v3/serviceList"
_KST = timezone(timedelta(hours=9))
_PER_PAGE = 100

# ---------------------------------------------------------------------------
# 금액 정규식 — KRW 표기 다양성 처리 (최대/월/연간 중 첫 번째 매칭)
# ---------------------------------------------------------------------------


def parse_krw_amount(text: str | None) -> int | None:
    """`지원내용` 텍스트에서 첫 KRW 금액을 원화 정수로 반환.

    우선순위: 억+만원 복합 > 억원 > 천만원 > 백만원 > 만원 > 5자리+ 원
    """
    if not text:
        return None
    # 공백·콤마 제거 (숫자 사이 콤마도 제거)
    clean = re.sub(r"[,\s]", "", text[:3000])
    m = re.search(r"(\d+)억(\d+)만원", clean)
    if m:
        return int(m.group(1)) * 100_000_000 + int(m.group(2)) * 10_000
    m = re.search(r"(\d+)억(\d+)천만원", clean)
    if m:
        return int(m.group(1)) * 100_000_000 + int(m.group(2)) * 10_000_000
    m = re.search(r"(\d+)억원", clean)
    if m:
        return int(m.group(1)) * 100_000_000
    m = re.search(r"(\d+)천만원", clean)
    if m:
        return int(m.group(1)) * 10_000_000
    m = re.search(r"(\d+)백만원", clean)
    if m:
        return int(m.group(1)) * 1_000_000
    m = re.search(r"(\d+)만원", clean)
    if m:
        v = int(m.group(1))
        return v * 10_000 if v > 0 else None
    # 원단위 — 5자리 이상 (9,999원 이하는 노이즈로 제외)
    m = re.search(r"(\d{5,})원", clean)
    if m:
        return int(m.group(1))
    return None


def parse_modified_at(dt_str: str | None) -> datetime | None:
    """YYYYMMDDHHmmss(14자리) or YYYYMMDD(8자리) → datetime KST."""
    if not dt_str:
        return None
    s = dt_str.strip()
    try:
        if len(s) >= 14:
            return datetime.strptime(s[:14], "%Y%m%d%H%M%S").replace(tzinfo=_KST)
        if len(s) >= 8:
            return datetime.strptime(s[:8], "%Y%m%d").replace(tzinfo=_KST)
    except ValueError:
        pass
    return None


# ---------------------------------------------------------------------------
# watermark
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Subsidy24Watermark:
    """증분 수집 기준 — 마지막으로 처리한 수정일시."""

    modified_at: datetime | None = None


# ---------------------------------------------------------------------------
# collector
# ---------------------------------------------------------------------------


class Subsidy24Collector:
    """gov24 v3 serviceList 정부 지원 서비스 수집기.

    증분 전략:
      watermark(수정일시) 이후 변경된 서비스만 수집.
      DB의 source_url UNIQUE 제약이 최종 멱등 보증을 담당하므로,
      watermark 를 구성 못 한 최초 수집도 안전하게 동작한다.
    """

    def __init__(self, service_key: str):
        if not service_key or not service_key.strip():
            raise ValueError("SUBSIDY24_SERVICE_KEY 가 비어 있습니다.")
        self._key = service_key.strip()

    async def collect(
        self,
        *,
        max_items: int = 500,
        watermark: Subsidy24Watermark | None = None,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        """gov24 serviceList 수집.

        Returns:
            (dtos, stats)
        """
        stats: dict[str, int] = {"fetched_total": 0, "parsed_amount": 0}
        kept: list[EconomicCollectDto] = []

        timeout = aiohttp.ClientTimeout(total=30)
        page = 1

        async with aiohttp.ClientSession(timeout=timeout) as session:
            while len(kept) < max_items:
                params: dict[str, Any] = {
                    "page": page,
                    "perPage": _PER_PAGE,
                    "serviceKey": self._key,
                }
                # 증분 필터 — 수정일시 GTE 워터마크
                if watermark and watermark.modified_at:
                    wm_str = watermark.modified_at.strftime("%Y%m%d%H%M%S")
                    params["cond[수정일시:GTE]"] = wm_str

                try:
                    async with session.get(_BASE_URL, params=params) as resp:
                        resp.raise_for_status()
                        data = await resp.json(content_type=None)
                except Exception:
                    logger.exception("[subsidy24] API 호출 실패 page=%s", page)
                    break

                items: list[dict[str, Any]] = data.get("data") or []
                total_count: int = int(data.get("matchCount") or data.get("totalCount") or 0)

                if not items:
                    break

                for item in items:
                    stats["fetched_total"] += 1
                    dto = self._to_dto(item)
                    if dto is None:
                        continue
                    if dto.investment_amount is not None:
                        stats["parsed_amount"] += 1
                    kept.append(dto)
                    if len(kept) >= max_items:
                        break

                # 페이지 종료 조건
                if len(kept) >= max_items or page * _PER_PAGE >= total_count:
                    break
                page += 1

        logger.info("[subsidy24] collected=%s stats=%s", len(kept), stats)
        return kept, stats

    def _to_dto(self, item: dict[str, Any]) -> EconomicCollectDto | None:
        svc_id = (item.get("서비스ID") or "").strip()
        if not svc_id:
            return None

        name = (item.get("서비스명") or "").strip()
        content = item.get("지원내용") or ""
        purpose = (item.get("서비스목적요약") or "").strip()
        category = (item.get("서비스분야") or "").strip()
        support_type = (item.get("지원유형") or "").strip()
        institution = (item.get("소관기관명") or "").strip()
        user_type = (item.get("사용자구분") or "").strip()
        detail_url = (item.get("상세조회URL") or "").strip()
        if not detail_url:
            detail_url = f"https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{svc_id}"

        modified_str = item.get("수정일시") or item.get("등록일시")
        modified_dt = parse_modified_at(modified_str)
        amount = parse_krw_amount(content)
        source_url = detail_url
        if modified_dt:
            version = modified_dt.strftime("%Y%m%d%H%M%S")
            source_url = f"{detail_url.split('#', 1)[0]}#modified={version}"

        raw_metadata: dict[str, Any] = {
            "service_id": svc_id,
            "service_category": category,
            "support_type": support_type,
            "institution_type": (item.get("소관기관유형") or "").strip() or None,
            "user_type": user_type,
            "purpose_summary": purpose[:500] if purpose else None,
            "support_content_snippet": content[:1000] if content else None,
            "eligibility_snippet": (item.get("선정기준") or "")[:500] or None,
            "application_period": (item.get("신청기한") or "").strip() or None,
            "modified_at_raw": modified_str,
            "collected_via": "subsidy24-api",
        }

        return EconomicCollectDto(
            source_type="GOVT_SUBSIDY24",
            source_url=source_url,
            raw_title=name[:500] if name else f"보조금24_{svc_id}",
            investor_name=institution or "정부",
            target_company_or_fund=user_type or None,
            investment_amount=amount,
            currency="KRW",
            raw_metadata=raw_metadata,
            published_at=modified_dt,
        )


__all__ = [
    "Subsidy24Collector",
    "Subsidy24Watermark",
    "parse_krw_amount",
    "parse_modified_at",
]
