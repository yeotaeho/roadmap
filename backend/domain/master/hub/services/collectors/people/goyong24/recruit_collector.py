# 고용24 채용정보 API에서 직종별 채용공고 수요(Demand) 신호를 수집한다

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from typing import Any

import aiohttp

from domain.master.models.transfer.people_collect_dto import PeopleCollectDto

logger = logging.getLogger(__name__)

# 고용24(work24) 채용정보 목록 오퍼레이션(210L01). 직업정보는 212L01, 채용정보는 210 계열.
# ⚠️ 채용정보 API는 **기업회원 전용** — 개인회원 authKey 는 "개인회원은 사용할 수 없는 OPEN-API"
#    에러 반환(2026-06-23 live 확인). 기업회원 key 또는 data.go.kr 워크넷 채용정보(3038225) 사용.
_API_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L01.do"
_SOURCE_TYPE = "PEOPLE_GOYONG24_RECRUIT"
_DATA_ROLE = "DEMAND_HIRING_SIGNAL"

# 응답 항목에서 직종명(집계 키)으로 매핑 가능한 후보 태그.
_JOB_FIELDS: tuple[str, ...] = (
    "jobsNm",
    "jobsCdKorNm",
    "jobNm",
    "occupation",
    "jobCdNm",
    "jobsCd",
)


def _find_lists(value: Any) -> list[list[dict[str, Any]]]:
    """중첩 구조에서 dict 리스트들을 모두 찾아낸다 (worknet 파서와 동일 전략)."""
    found: list[list[dict[str, Any]]] = []
    if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
        found.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(_find_lists(child))
    return found


def parse_recruit_payload(payload: str) -> list[dict[str, Any]]:
    """XML/JSON 어느 쪽이 와도 채용공고 dict 리스트로 정규화."""
    text = (payload or "").lstrip()
    if not text:
        return []
    if text.startswith(("{", "[")):
        parsed = json.loads(payload)
        candidates = _find_lists(parsed)
        return max(candidates, key=len, default=[])

    root = ET.fromstring(payload)
    rows: list[dict[str, Any]] = []
    # work24 채용정보 응답의 반복 단위 후보 (wanted/dhsOpenEmpInfo 등) — 자식이 있는 노드를 폭넓게 수집.
    for node in root.iter():
        children = list(node)
        if not children:
            continue
        row = {
            child.tag.split("}")[-1]: (child.text or "").strip()
            for child in children
            if not list(child)
        }
        if row and any(f in row for f in _JOB_FIELDS):
            rows.append(row)
    return rows


def _pick(item: dict[str, Any], fields: tuple[str, ...]) -> str:
    for f in fields:
        value = item.get(f)
        if value is None:
            continue
        s = str(value).strip()
        if s:
            return s
    return ""


def aggregate_recruit_demand(
    items: list[dict[str, Any]], reference_date: date
) -> list[PeopleCollectDto]:
    """채용공고 목록을 직종별 건수로 집계 → 직종당 1행 (Demand 신호)."""
    counter: Counter[str] = Counter()
    for item in items:
        job = _pick(item, _JOB_FIELDS) or "미분류"
        counter[job[:100]] += 1

    rows: list[PeopleCollectDto] = []
    for job_name, count in counter.most_common():
        rows.append(
            PeopleCollectDto(
                source_type=_SOURCE_TYPE,
                source_url=f"{_API_URL}?target=RECRUIT&jobsNm={job_name}",
                keyword_or_job=job_name,
                search_volume_or_count=count,
                raw_metadata={
                    "data_role": _DATA_ROLE,
                    "scanned_total": len(items),
                },
                reference_date=reference_date,
            )
        )
    return rows


class Goyong24RecruitCollector:
    """고용24 채용정보 — 최근 공고를 페이지 순회 후 직종별 건수로 집계."""

    def __init__(self, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("GOYONG24_RECRUIT_API_KEY가 설정되어 있지 않습니다.")
        self._key = api_key.strip()

    async def collect(
        self,
        *,
        reference_date: date | None = None,
        max_pages: int = 5,
        display: int = 100,
    ) -> tuple[list[PeopleCollectDto], dict[str, int]]:
        target_date = reference_date or date.today()
        stats = {"requests_total": 0, "requests_ok": 0, "errors": 0, "scanned": 0, "fetched": 0}
        items: list[dict[str, Any]] = []
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for page in range(1, max_pages + 1):
                stats["requests_total"] += 1
                params = {
                    "authKey": self._key,
                    "returnType": "XML",
                    "callTp": "L",
                    "startPage": str(page),
                    "display": str(min(display, 100)),
                }
                try:
                    async with session.get(_API_URL, params=params) as response:
                        response.raise_for_status()
                        payload = await response.text()
                    page_items = parse_recruit_payload(payload)
                    stats["requests_ok"] += 1
                except Exception:
                    stats["errors"] += 1
                    logger.exception("[goyong24-recruit] 채용정보 수집 실패 page=%s", page)
                    break
                if not page_items:
                    break
                items.extend(page_items)
                if len(page_items) < min(display, 100):
                    break

        stats["scanned"] = len(items)
        rows = aggregate_recruit_demand(items, target_date)
        stats["fetched"] = len(rows)
        return rows, stats


__all__ = [
    "Goyong24RecruitCollector",
    "parse_recruit_payload",
    "aggregate_recruit_demand",
]
