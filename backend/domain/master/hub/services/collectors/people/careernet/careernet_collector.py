"""커리어넷 Open API로 직업정보(발전가능성·연봉·유사직업 포함)와 학과정보를 수집한다.

API 등록: https://www.career.go.kr Open API 센터 → 인증키 발급 (apiKey)
엔드포인트: https://www.career.go.kr/cnet/openapi/getOpenApi
공통 파라미터: apiKey, svcType=api, contentType=json, perPage, thisPage
직업정보: svcCode=JOB, gubun=job_dic_list (gubun 파라미터는 실제로 무시됨)
  유효 응답필드: job(직업명), jobdicSeq(코드), summary(설명), profession(분야),
                salery(연봉구간), possibility(발전가능성: 매우좋음/보통미만 등),
                similarJob(유사직업), totalCount
  ※ prospect(일자리전망) 필드는 API에서 항상 빈 문자열로 반환됨 — 수집 불가
학과정보: svcCode=MAJOR, gubun=univ_list
수집 주기: 월간 (직업/학과 데이터는 거의 정적)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from typing import Any

import aiohttp

from domain.master.models.transfer.people_collect_dto import PeopleCollectDto

logger = logging.getLogger(__name__)

_API_URL = "https://www.career.go.kr/cnet/openapi/getOpenApi"

# (svc_code, gubun, source_type, name_fields, code_field)
# name_fields: 응답에서 직업/학과명을 찾는 필드 우선순위 (버전별 상이 대비)
_JOB_SPEC = {
    "svc_code": "JOB",
    "gubun": "job_dic_list",
    "source_type": "PEOPLE_CAREERNET_JOB",
    "name_fields": ("job", "jobNm", "jobName"),
    "code_field": "jobdicSeq",
    "data_role": "JOB_TAXONOMY_SIGNAL",  # possibility·salery·profession 기반, prospect는 API 미제공
}
_MAJOR_SPEC = {
    "svc_code": "MAJOR",
    "gubun": "univ_list",
    "source_type": "PEOPLE_CAREERNET_MAJOR",
    "name_fields": ("major", "mClass", "facilName", "majorNm"),
    "code_field": "majorSeq",
    "data_role": "MAJOR_DEMAND_SIGNAL",
}


def _find_result_list(parsed: Any) -> list[dict[str, Any]]:
    """커리어넷 JSON 응답에서 항목 배열을 추출한다."""
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        # 흔한 래핑 키 우선 탐색
        for key in ("content", "dataSearch", "result", "list", "jobList", "majorList"):
            child = parsed.get(key)
            found = _find_result_list(child) if child is not None else []
            if found:
                return found
        for child in parsed.values():
            found = _find_result_list(child)
            if found:
                return found
    return []


def parse_careernet_payload(payload: str) -> tuple[list[dict[str, Any]], int]:
    """(항목 리스트, totalCount)를 반환한다."""
    text = payload.lstrip()
    if not text.startswith(("{", "[")):
        logger.warning("[careernet] JSON이 아닌 응답 — 일부: %.150s", text)
        return [], 0
    parsed = json.loads(payload)
    items = _find_result_list(parsed)
    total = 0
    if isinstance(parsed, dict):
        for key in ("totalCount", "total", "totCnt"):
            val = _deep_get(parsed, key)
            if val is not None:
                try:
                    total = int(str(val).replace(",", ""))
                except (TypeError, ValueError):
                    total = 0
                break
    return items, total


def _deep_get(data: Any, target_key: str) -> Any:
    if isinstance(data, dict):
        if target_key in data:
            return data[target_key]
        for child in data.values():
            found = _deep_get(child, target_key)
            if found is not None:
                return found
    return None


def _pick_name(item: dict[str, Any], name_fields: tuple[str, ...]) -> str:
    for field in name_fields:
        value = str(item.get(field) or "").strip()
        if value:
            return value
    return ""


def careernet_item_to_dto(
    item: dict[str, Any], spec: dict[str, Any], reference_date: date
) -> PeopleCollectDto | None:
    name = _pick_name(item, spec["name_fields"])
    if not name:
        return None
    code = str(item.get(spec["code_field"]) or "").strip()
    metadata: dict[str, Any] = {
        "careernet_code": code or None,
        "data_role": spec["data_role"],
    }
    # 직업정보의 핵심 신호 필드 보존 (일자리전망 = 직업전망 대체)
    for field in ("summary", "profession", "salery", "prospect", "possibility", "similarJob"):
        value = str(item.get(field) or "").strip()
        if value:
            metadata[field] = value[:1000]

    return PeopleCollectDto(
        source_type=spec["source_type"],
        source_url=f"{_API_URL}?svcCode={spec['svc_code']}&seq={code}",
        keyword_or_job=name[:100],
        search_volume_or_count=None,
        raw_metadata=metadata,
        reference_date=reference_date,
    )


class CareernetCollector:
    """커리어넷 직업정보·학과정보 수집기.

    apiKey 없으면 ValueError를 즉시 raise한다 (Ingest Service에서 HTTP 400 변환).
    """

    def __init__(self, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("CAREERNET_API_KEY가 설정되어 있지 않습니다.")
        self._key = api_key.strip()

    async def collect(
        self,
        *,
        reference_date: date | None = None,
        include_major: bool = True,
        per_page: int = 100,
        max_pages: int = 50,
        sleep_seconds: float = 0.3,
    ) -> tuple[list[PeopleCollectDto], dict[str, int]]:
        target_date = reference_date or date.today()
        specs = [_JOB_SPEC] + ([_MAJOR_SPEC] if include_major else [])
        stats = {"specs_total": len(specs), "specs_ok": 0, "errors": 0, "fetched": 0}
        rows: list[PeopleCollectDto] = []
        timeout = aiohttp.ClientTimeout(total=25)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for spec in specs:
                try:
                    spec_rows = await self._fetch_all_pages(
                        session, spec, target_date, per_page, max_pages, sleep_seconds
                    )
                    rows.extend(spec_rows)
                    stats["specs_ok"] += 1
                except Exception:
                    stats["errors"] += 1
                    logger.exception("[careernet] svcCode=%s 수집 실패", spec["svc_code"])

        stats["fetched"] = len(rows)
        logger.info("[careernet] 수집 완료 %d건", len(rows))
        return rows, stats

    async def _fetch_all_pages(
        self,
        session: aiohttp.ClientSession,
        spec: dict[str, Any],
        reference_date: date,
        per_page: int,
        max_pages: int,
        sleep_seconds: float,
    ) -> list[PeopleCollectDto]:
        rows: list[PeopleCollectDto] = []
        total_count = 0
        page = 1
        while page <= max_pages:
            params = {
                "apiKey": self._key,
                "svcType": "api",
                "svcCode": spec["svc_code"],
                "contentType": "json",
                "gubun": spec["gubun"],
                "perPage": str(per_page),
                "thisPage": str(page),
            }
            async with session.get(_API_URL, params=params) as resp:
                resp.raise_for_status()
                payload = await resp.text()

            items, total = parse_careernet_payload(payload)
            if page == 1 and total:
                total_count = total
            for item in items:
                dto = careernet_item_to_dto(item, spec, reference_date)
                if dto:
                    rows.append(dto)

            # 종료 조건: 빈 페이지, perPage 미만 수신, 또는 totalCount 도달
            if not items or len(items) < per_page:
                break
            if total_count and len(rows) >= total_count:
                break
            page += 1
            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)
        return rows


__all__ = [
    "CareernetCollector",
    "parse_careernet_payload",
    "careernet_item_to_dto",
    "_JOB_SPEC",
    "_MAJOR_SPEC",
]
