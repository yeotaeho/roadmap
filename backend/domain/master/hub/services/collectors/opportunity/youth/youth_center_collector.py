# 온통청년 청년센터 OpenAPI Bronze 수집 — youthcenter.go.kr/opi/youthCntrList.do

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any, Optional

import aiohttp

from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "OPP_YOUTH_CENTER"
_BASE_URL = "https://www.youthcenter.go.kr/opi/youthCntrList.do"


def _parse_item(elem: ET.Element) -> Optional[OpportunityCollectDto]:
    def t(tag: str) -> str:
        node = elem.find(tag)
        return (node.text or "").strip() if node is not None else ""

    # 센터명 — 공식 필드: cntrNm
    raw_title = t("cntrNm") or t("centerName") or t("name")
    if not raw_title:
        return None

    center_id = t("cntrId") or t("id") or ""
    source_url = (
        f"https://www.youthcenter.go.kr/youth/center/detail/{center_id}"
        if center_id
        else _BASE_URL
    )

    # 주소 — 공식 필드: rdnmadr (도로명주소)
    address = t("rdnmadr") or t("lnmadr") or t("address") or ""
    raw_content = address or None

    raw_metadata: dict[str, Any] = {
        "center_id": center_id,
        "tel": t("phoneNumber") or t("tel"),
        "sido": t("ctpvNm") or t("sido"),
        "sigungu": t("signguNm") or t("sigungu"),
        "homepage": t("homepageUrl") or t("url"),
        "address": address,
    }

    return OpportunityCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=source_url,
        raw_title=raw_title[:500],
        host_name="온통청년",
        raw_content=raw_content,
        raw_metadata=raw_metadata,
        published_at=None,
        deadline_at=None,
    )


class YouthCenterCollector:
    """온통청년 청년센터 OpenAPI Collector — 오프라인 지원기관 마스터.

    BASE_URL: https://www.youthcenter.go.kr/opi/youthCntrList.do
    인증: openApiVlak (UUID 36자)  /  응답: XML
    """

    def __init__(self, service_key: str) -> None:
        if not service_key or not service_key.strip():
            raise ValueError("YOUTH_CENTER_SERVICE_KEY 가 비어 있습니다.")
        self._service_key = service_key.strip()

    async def collect(self, *, max_items: int = 1000) -> tuple[list[OpportunityCollectDto], dict[str, int | str]]:
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
                            logger.error("온통청년 청년센터 HTTP %d", resp.status)
                            break
                        xml_text = await resp.text(encoding="utf-8")
                except Exception:
                    logger.exception("온통청년 청년센터 네트워크 오류 (page=%d)", page_no)
                    break

                try:
                    root = ET.fromstring(xml_text)
                except ET.ParseError:
                    logger.error("온통청년 청년센터 XML 파싱 실패")
                    break

                items = root.findall(".//youthCenter") or root.findall(".//item") or list(root)
                if not items:
                    break

                for elem in items:
                    try:
                        dto = _parse_item(elem)
                    except Exception:
                        logger.warning("온통청년 청년센터 아이템 파싱 오류, 스킵")
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
        logger.info("온통청년 청년센터 수집 완료: %s", stats)
        return collected, stats


__all__ = ["YouthCenterCollector"]
