"""고용24 직업정보 API에서 직업 분류와 직업명 원천을 수집한다."""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

import aiohttp

from domain.master.models.transfer.people_collect_dto import PeopleCollectDto

logger = logging.getLogger(__name__)

_API_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo212L01.do"
_SOURCE_TYPE = "PEOPLE_WORKNET_JOB"


def _find_lists(value: Any) -> list[list[dict[str, Any]]]:
    found: list[list[dict[str, Any]]] = []
    if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
        found.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(_find_lists(child))
    return found


def parse_worknet_payload(payload: str) -> list[dict[str, Any]]:
    text = payload.lstrip()
    if text.startswith(("{", "[")):
        parsed = json.loads(payload)
        candidates = _find_lists(parsed)
        return max(candidates, key=len, default=[])

    root = ET.fromstring(payload)
    rows: list[dict[str, Any]] = []
    for node in root.findall(".//jobList") + root.findall(".//job"):
        row = {child.tag.split("}")[-1]: (child.text or "").strip() for child in node}
        if row:
            rows.append(row)
    return rows


def worknet_item_to_dto(
    item: dict[str, Any], reference_date: date
) -> PeopleCollectDto | None:
    job_name = str(
        item.get("jobNm")
        or item.get("jobName")
        or item.get("dJobNm")
        or item.get("jobClcdNM")
        or ""
    ).strip()
    if not job_name:
        return None
    job_code = str(item.get("jobCd") or "").strip()
    category_code = str(item.get("jobClcd") or "").strip()
    category_name = str(item.get("jobClcdNM") or "").strip()
    return PeopleCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=f"{_API_URL}?target=JOBCD&jobCd={job_code}",
        keyword_or_job=job_name[:100],
        search_volume_or_count=None,
        raw_metadata={
            "job_code": job_code or None,
            "job_category_code": category_code or None,
            "job_category_name": category_name or None,
            "data_role": "JOB_TAXONOMY_SIGNAL",
        },
        reference_date=reference_date,
    )


class WorknetJobInfoCollector:
    def __init__(self, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("WORKNET_API_KEY가 설정되어 있지 않습니다.")
        self._key = api_key.strip()

    async def collect(
        self,
        *,
        reference_date: date | None = None,
    ) -> tuple[list[PeopleCollectDto], dict[str, int]]:
        target_date = reference_date or date.today()
        stats = {"requests_total": 1, "requests_ok": 0, "errors": 0, "fetched": 0}
        rows: list[PeopleCollectDto] = []
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            params = {
                "authKey": self._key,
                "returnType": "XML",
                "target": "JOBCD",
            }
            try:
                async with session.get(_API_URL, params=params) as response:
                    response.raise_for_status()
                    payload = await response.text()
                for item in parse_worknet_payload(payload):
                    dto = worknet_item_to_dto(item, target_date)
                    if dto:
                        rows.append(dto)
                stats["requests_ok"] = 1
            except Exception:
                stats["errors"] = 1
                logger.exception("[work24-job] 직업정보 수집 실패")
        stats["fetched"] = len(rows)
        return rows, stats


__all__ = [
    "WorknetJobInfoCollector",
    "parse_worknet_payload",
    "worknet_item_to_dto",
]
