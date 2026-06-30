# 온통청년 기본계획정책방향 OpenAPI Bronze 수집 — 거시 정책 방향 시그널

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "OPP_YOUTH_POLICY_DIRECTION"
_BASE_URL = "https://www.youthcenter.go.kr/opi/youthBplnPlcyDrctnList.do"


def _parse_date(raw: str | None) -> Optional[datetime]:
    if not raw:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            continue
    return None


def _parse_item(elem: ET.Element) -> Optional[OpportunityCollectDto]:
    def t(tag: str) -> str:
        node = elem.find(tag)
        return (node.text or "").strip() if node is not None else ""

    # 정책방향 제목 — 공식 필드: plcyDrctnTtl
    raw_title = t("plcyDrctnTtl") or t("directionTitle") or t("title")
    if not raw_title:
        return None

    direction_id = t("plcyDrctnId") or t("id") or ""
    source_url = (
        f"https://www.youthcenter.go.kr/youngPlcy/bplnPlcyDrctn/detail/{direction_id}"
        if direction_id
        else _BASE_URL
    )

    raw_content = t("plcyDrctnCn") or t("content") or None
    published_at = _parse_date(t("registDt") or t("pubDate"))

    raw_metadata: dict[str, Any] = {
        "direction_id": direction_id,
        "plan_year": t("bplnYear") or t("year"),    # 기본계획 연도
        "sector": t("taskClsfNm") or t("sector"),   # 과제 분류
        "ministry": t("chrgInstNm") or t("ministry"),  # 담당 부처
    }

    return OpportunityCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=source_url,
        raw_title=raw_title[:500],
        host_name=t("chrgInstNm") or "온통청년",
        raw_content=raw_content,
        raw_metadata=raw_metadata,
        published_at=published_at,
        deadline_at=None,
    )


class YouthPolicyDirectionCollector:
    """온통청년 기본계획정책방향 OpenAPI Collector — 거시 정책 방향 수집.

    BASE_URL: https://www.youthcenter.go.kr/opi/youthBplnPlcyDrctnList.do
    인증: openApiVlak (UUID 36자)  /  응답: XML
    Gap 섹터별 투자 시그널 보강 목적으로 활용.
    """

    def __init__(self, service_key: str) -> None:
        if not service_key or not service_key.strip():
            raise ValueError("YOUTH_BASIC_PLAN_SERVICE_KEY 가 비어 있습니다.")
        self._service_key = service_key.strip()

    async def collect(self, *, max_items: int = 200) -> tuple[list[OpportunityCollectDto], dict[str, int | str]]:
        page_no = 1
        per_page = min(max_items, 100)
        collected: list[OpportunityCollectDto] = []
        seen: set[str] = set()
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            while len(collected) < max_items:
                params = {
                    "openApiVlak": self._service_key,
                    "pageIndex": str(page_no),
                    "display": str(per_page),
                }
                try:
                    async with session.get(_BASE_URL, params=params) as resp:
                        if resp.status != 200:
                            logger.error("온통청년 기본계획 HTTP %d", resp.status)
                            break
                        xml_text = await resp.text(encoding="utf-8")
                except Exception:
                    logger.exception("온통청년 기본계획 네트워크 오류 (page=%d)", page_no)
                    break

                try:
                    root = ET.fromstring(xml_text)
                except ET.ParseError:
                    logger.error("온통청년 기본계획 XML 파싱 실패")
                    break

                items = root.findall(".//policyDirection") or root.findall(".//item") or list(root)
                if not items:
                    break

                for elem in items:
                    try:
                        dto = _parse_item(elem)
                    except Exception:
                        logger.warning("온통청년 기본계획 아이템 파싱 오류, 스킵")
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

        stats: dict[str, int | str] = {
            "pages_fetched": page_no,
            "items_collected": len(collected),
        }
        logger.info("온통청년 기본계획 수집 완료: %s", stats)
        return collected, stats


__all__ = ["YouthPolicyDirectionCollector"]
