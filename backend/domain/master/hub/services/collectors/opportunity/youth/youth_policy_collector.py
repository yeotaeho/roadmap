# 온통청년 청년정책 OpenAPI Bronze 수집 — youthcenter.go.kr/opi/youthPlcyList.do

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "OPP_YOUTH_POLICY"
_BASE_URL = "https://www.youthcenter.go.kr/opi/youthPlcyList.do"

# 온통청년 공식 API 문서 기준 필드명 (2024-12 신버전, data.go.kr 15143273)
# 응답 형식: XML  /  인증 파라미터: openApiVlak (UUID)
# 페이지네이션: pageIndex(1-based) + display(페이지당 건수)


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

    # 정책명 — 공식 필드: plcyNm
    raw_title = t("plcyNm") or t("polyNm") or t("title")
    if not raw_title:
        return None

    # 정책 고유번호 — 공식 필드: plcyNo
    policy_no = t("plcyNo") or t("polyNo") or t("id")
    source_url = (
        f"https://www.youthcenter.go.kr/youngPlcy/youngPlcyUnif/{policy_no}"
        if policy_no
        else _BASE_URL
    )

    # 주관기관명 — 공식 필드: sprvInstNm
    host_name = t("sprvInstNm") or t("institNm") or "온통청년"

    # 정책 내용 — 공식 필드: plcyCn
    raw_content = t("plcyCn") or t("polyBizSjnm") or None

    # 날짜 — 신청 시작/종료일
    published_at = _parse_date(t("aplySttDt") or t("rgsttDt"))
    deadline_at = _parse_date(t("aplyEndDt") or t("deadlineDate"))

    raw_metadata: dict[str, Any] = {
        "policy_no": policy_no,
        "policy_type": t("plcyClsfNm") or t("polyRlmCd"),  # 정책분류명
        "target_group": t("aplyTrgtNm") or t("ageInfo"),   # 신청대상
        "support_scale": t("sprtScl"),                      # 지원규모
        "area": t("lclsfNm") or t("srchPolyBizSecd"),       # 지역
        "keyword": t("keyword"),
    }

    return OpportunityCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=source_url,
        raw_title=raw_title[:500],
        host_name=host_name[:150],
        raw_content=raw_content,
        raw_metadata=raw_metadata,
        published_at=published_at,
        deadline_at=deadline_at,
    )


class YouthPolicyCollector:
    """온통청년 청년정책 OpenAPI Collector.

    BASE_URL: https://www.youthcenter.go.kr/opi/youthPlcyList.do
    인증: openApiVlak (UUID 36자)
    응답: XML  /  페이지네이션: pageIndex + display
    참고: data.go.kr 15143273 (한국고용정보원_온통청년_청년정책API)
    """

    def __init__(self, service_key: str) -> None:
        if not service_key or not service_key.strip():
            raise ValueError("YOUTH_POLICY_SERVICE_KEY 가 비어 있습니다.")
        self._service_key = service_key.strip()

    async def collect(self, *, max_items: int = 500) -> tuple[list[OpportunityCollectDto], dict[str, int | str]]:
        page_no = 1
        per_page = min(max_items, 100)
        collected: list[OpportunityCollectDto] = []
        seen: set[str] = set()
        timeout = aiohttp.ClientTimeout(total=30)
        failed_pages = 0

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
                            logger.error("온통청년 청년정책 HTTP %d (page=%d)", resp.status, page_no)
                            break
                        xml_text = await resp.text(encoding="utf-8")
                except Exception:
                    logger.exception("온통청년 청년정책 네트워크 오류 (page=%d)", page_no)
                    failed_pages += 1
                    if failed_pages >= 3:
                        break
                    continue

                try:
                    root = ET.fromstring(xml_text)
                except ET.ParseError:
                    logger.error("온통청년 청년정책 XML 파싱 실패 (page=%d)", page_no)
                    break

                # 응답 래퍼 구조: <youthPolicy><list><정책항목들>
                # 또는 <response><body><items><item>...</item></items></body></response>
                items = (
                    root.findall(".//youthPolicy")
                    or root.findall(".//item")
                    or list(root)
                )

                if not items:
                    break

                for elem in items:
                    try:
                        dto = _parse_item(elem)
                    except Exception:
                        logger.warning("온통청년 청년정책 아이템 파싱 오류, 스킵")
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
            "failed_pages": failed_pages,
        }
        logger.info("온통청년 청년정책 수집 완료: %s", stats)
        return collected, stats


__all__ = ["YouthPolicyCollector"]
