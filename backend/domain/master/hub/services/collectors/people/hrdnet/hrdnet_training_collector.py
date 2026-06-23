"""HRD-Net 훈련과정 API에서 직종별 국가 훈련 수요를 수집한다."""

from __future__ import annotations

import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any

import aiohttp

from domain.master.models.transfer.people_collect_dto import PeopleCollectDto

logger = logging.getLogger(__name__)

_API_URL = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"
_SOURCE_TYPE = "PEOPLE_HRDNET_TRAINING"
_NCS_TRAINING_SECTORS: list[tuple[str, str]] = [
    ("ICT_SW", "20"),
    ("ICT_HW", "21"),
    ("MANUFACTURING", "15"),
    ("FOOD", "07"),
    ("BEAUTY", "12"),
    ("SOCIAL_WELFARE", "23"),
    ("EDUCATION", "24"),
    ("CONSTRUCTION", "04"),
    ("HEALTH", "08"),
    ("DESIGN", "02"),
    ("CULTURE_ARTS", "01"),
    ("LOGISTICS", "22"),
]


def _flatten_candidate_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("srchList", "items", "item", "data", "records"):
            if key in value:
                rows = _flatten_candidate_items(value[key])
                if rows:
                    return rows
        for child in value.values():
            rows = _flatten_candidate_items(child)
            if rows:
                return rows
    return []


def parse_hrdnet_payload(payload: str) -> list[dict[str, Any]]:
    text = payload.lstrip()
    if text.startswith(("{", "[")):
        return _flatten_candidate_items(json.loads(payload))
    root = ET.fromstring(payload)
    rows: list[dict[str, Any]] = []
    for node in root.findall(".//scn_list") + root.findall(".//item"):
        row = {child.tag.split("}")[-1]: (child.text or "").strip() for child in node}
        if row:
            rows.append(row)
    return rows


def _to_int(value: Any) -> int:
    try:
        return int(float(str(value or "0").replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _extract_hrdnet_total_count(payload: str) -> int:
    """HRD-Net 응답에서 전체 과정 수(totalCount)를 추출한다."""
    text = payload.lstrip()
    if text.startswith(("{", "[")):
        data = json.loads(payload)
        for key in ("totalCount", "totCnt", "total_count", "tot_count"):
            if isinstance(data, dict):
                val = data.get(key)
                if val is not None:
                    return _to_int(val)
                for child in data.values():
                    if isinstance(child, dict):
                        val2 = child.get(key)
                        if val2 is not None:
                            return _to_int(val2)
        return 0
    root = ET.fromstring(payload)
    for tag in ("totCnt", "totalCount", "total_count"):
        node = root.find(f".//{tag}")
        if node is not None and node.text:
            return _to_int(node.text)
    return 0


def aggregate_hrdnet_sector(
    items: list[dict[str, Any]], sector_name: str, ncs_code: str, reference_date: date
) -> PeopleCollectDto:
    # work24 API 응답 필드명이 버전별로 상이해 OR 체인으로 시도
    # 확인된 필드: trprDegrCost(훈련비), totFxnum(정원) — 미매핑 시 0
    total_cost = sum(
        _to_int(item.get("trprDegrCost") or item.get("courseMan") or item.get("realMan"))
        for item in items
    )
    trainee_capacity = sum(
        _to_int(item.get("totFxnum") or item.get("yardMan") or item.get("trprChap"))
        for item in items
    )
    if items and total_cost == 0:
        logger.warning(
            "[hrdnet] sector=%s(%s) 훈련비 집계 0 — API 응답 필드명 확인 필요. 첫 레코드 키: %s",
            sector_name, ncs_code, list(items[0].keys())[:10],
        )
    return PeopleCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=f"{_API_URL}?srchNcs1={ncs_code}",
        keyword_or_job=sector_name[:100],
        search_volume_or_count=len(items),
        raw_metadata={
            "ncs_code": ncs_code,
            "sector_name": sector_name,
            "total_training_cost": total_cost,
            "trainee_capacity": trainee_capacity,
            "sample_courses": [
                item.get("title") or item.get("trprNm") or item.get("trainstCstId")
                for item in items[:5]
            ],
            "data_role": "TRAINING_DEMAND_SIGNAL",
        },
        reference_date=reference_date,
    )


class HrdnetTrainingCollector:
    def __init__(self, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("HRDNET_API_KEY가 설정되어 있지 않습니다.")
        self._key = api_key.strip()

    async def collect(
        self,
        *,
        reference_date: date | None = None,
        sectors: list[tuple[str, str]] | None = None,
        sleep_seconds: float = 0.2,
        page_size: int = 100,
    ) -> tuple[list[PeopleCollectDto], dict[str, int]]:
        target_date = reference_date or date.today()
        search_end_date = target_date + timedelta(days=90)
        targets = sectors or _NCS_TRAINING_SECTORS
        stats = {"sectors_total": len(targets), "sectors_ok": 0, "errors": 0, "fetched": 0}
        rows: list[PeopleCollectDto] = []
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for index, (sector_name, ncs_code) in enumerate(targets):
                base_params = {
                    "authKey": self._key,
                    "returnType": "XML",
                    "outType": "1",
                    "pageSize": str(page_size),
                    "srchTraStDt": target_date.strftime("%Y%m%d"),
                    "srchTraEndDt": search_end_date.strftime("%Y%m%d"),
                    "sort": "ASC",
                    "sortCol": "2",
                    "srchNcs1": ncs_code,
                }
                try:
                    items = await self._fetch_all_pages(
                        session, base_params, page_size, sleep_seconds
                    )
                    rows.append(
                        aggregate_hrdnet_sector(items, sector_name, ncs_code, target_date)
                    )
                    stats["sectors_ok"] += 1
                except Exception:
                    stats["errors"] += 1
                    logger.exception("[hrdnet] ncs=%s 수집 실패", ncs_code)
                if index < len(targets) - 1 and sleep_seconds > 0:
                    await asyncio.sleep(sleep_seconds)
        stats["fetched"] = len(rows)
        return rows, stats

    async def _fetch_all_pages(
        self,
        session: aiohttp.ClientSession,
        base_params: dict[str, str],
        page_size: int,
        sleep_seconds: float,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        total_count: int = 0
        page_num = 1
        while True:
            params = {**base_params, "pageNum": str(page_num)}
            async with session.get(_API_URL, params=params) as resp:
                resp.raise_for_status()
                payload = await resp.text()
            page_items = parse_hrdnet_payload(payload)
            items.extend(page_items)
            if page_num == 1:
                total_count = _extract_hrdnet_total_count(payload)
            # 마지막 페이지 조건: 페이지 미만 수신, 또는 totalCount 도달
            if len(page_items) < page_size:
                break
            if total_count and len(items) >= total_count:
                break
            page_num += 1
            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)
        return items


__all__ = [
    "HrdnetTrainingCollector",
    "parse_hrdnet_payload",
    "aggregate_hrdnet_sector",
    "_NCS_TRAINING_SECTORS",
]
