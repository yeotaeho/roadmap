# 온통청년 청년콘텐츠 OpenAPI Bronze 수집 — youthcenter.go.kr/opi/youthCntnList.do

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "OPP_YOUTH_CONTENT"
_BASE_URL = "https://www.youthcenter.go.kr/opi/youthCntnList.do"


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

    # 콘텐츠 제목 — 공식 필드: cntnTtl
    raw_title = t("cntnTtl") or t("title") or t("subject")
    if not raw_title:
        return None

    content_id = t("cntnId") or t("id") or ""
    source_url = (
        f"https://www.youthcenter.go.kr/youth/content/detail/{content_id}"
        if content_id
        else _BASE_URL
    )

    raw_content = t("cntnCn") or t("content") or t("summary") or None
    published_at = _parse_date(t("registDt") or t("pubDate"))

    raw_metadata: dict[str, Any] = {
        "content_id": content_id,
        "content_type": t("cntnClsfNm") or t("type"),
        "tag": t("tag") or t("keyword"),
        "view_count": t("inqCnt") or t("viewCount"),
    }

    return OpportunityCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=source_url,
        raw_title=raw_title[:500],
        host_name="온통청년",
        raw_content=raw_content,
        raw_metadata=raw_metadata,
        published_at=published_at,
        deadline_at=None,
    )


class YouthContentCollector:
    """온통청년 청년콘텐츠 OpenAPI Collector — 카드뉴스·영상·기사 등.

    BASE_URL: https://www.youthcenter.go.kr/opi/youthCntnList.do
    인증: openApiVlak (UUID 36자)  /  응답: XML
    """

    def __init__(self, service_key: str) -> None:
        if not service_key or not service_key.strip():
            raise ValueError("YOUTH_CONTENT_SERVICE_KEY 가 비어 있습니다.")
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
                            logger.error("온통청년 청년콘텐츠 HTTP %d", resp.status)
                            break
                        xml_text = await resp.text(encoding="utf-8")
                except Exception:
                    logger.exception("온통청년 청년콘텐츠 네트워크 오류 (page=%d)", page_no)
                    break

                try:
                    root = ET.fromstring(xml_text)
                except ET.ParseError:
                    logger.error("온통청년 청년콘텐츠 XML 파싱 실패")
                    break

                items = root.findall(".//youthContent") or root.findall(".//item") or list(root)
                if not items:
                    break

                for elem in items:
                    try:
                        dto = _parse_item(elem)
                    except Exception:
                        logger.warning("온통청년 청년콘텐츠 아이템 파싱 오류, 스킵")
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
        logger.info("온통청년 청년콘텐츠 수집 완료: %s", stats)
        return collected, stats


__all__ = ["YouthContentCollector"]
