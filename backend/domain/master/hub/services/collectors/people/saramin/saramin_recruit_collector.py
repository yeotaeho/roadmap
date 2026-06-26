# 사람인 채용정보 API에서 키워드별 채용공고 수요(Demand) 신호를 수집한다

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import aiohttp

from domain.master.models.transfer.people_collect_dto import PeopleCollectDto

logger = logging.getLogger(__name__)

# 사람인 채용정보 API (일 500콜 한도). 키워드별 jobs.total 만 읽어 한도를 아낀다.
#   문서: https://oapi.saramin.co.kr/guide/job-search
_API_URL = "https://oapi.saramin.co.kr/job-search"
_SOURCE_TYPE = "PEOPLE_SARAMIN_RECRUIT"
_DATA_ROLE = "DEMAND_HIRING_SIGNAL"

# 섹터 축에 대응하는 채용 수요 키워드 (어떤 산업이 뜨는가).
_KEYWORDS: tuple[str, ...] = (
    "인공지능",
    "데이터분석",
    "반도체",
    "바이오",
    "이차전지",
    "핀테크",
    "콘텐츠",
    "에듀테크",
    "물류",
    "뷰티",
)

# 직무·역량 단위 수요 키워드 (어떤 '직무·스킬'이 뜨는가 — 청년 진로의 결정적 선행 신호).
#   섹터 축이 잡지 못하는 직무 해상도를 보강한다(평가 ⑤b).
_JOB_KEYWORDS: tuple[str, ...] = (
    "데이터엔지니어",
    "머신러닝엔지니어",
    "백엔드개발자",
    "프론트엔드개발자",
    "데브옵스",
    "클라우드엔지니어",
    "프로덕트매니저",
    "UXUI디자이너",
    "정보보안",
    "QA엔지니어",
    "안드로이드개발자",
    "iOS개발자",
    "풀스택개발자",
    "그로스마케터",
)

# 기본 수집 대상 = 섹터 + 직무 키워드 (일 500콜 한도 내, 약 24키워드).
_DEFAULT_KEYWORDS: tuple[str, ...] = _KEYWORDS + _JOB_KEYWORDS


def parse_total(payload: dict[str, Any]) -> int | None:
    """사람인 응답(JSON)에서 jobs.total 정수 추출."""
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, dict):
        return None
    total = jobs.get("total")
    if total is None:
        return None
    try:
        return int(str(total).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


class SaraminRecruitCollector:
    """사람인 채용 — 키워드별 공고 총건수 집계 (키워드당 1행)."""

    def __init__(self, access_key: str) -> None:
        if not access_key or not access_key.strip():
            raise ValueError("SARAMIN_ACCESS_KEY가 설정되어 있지 않습니다.")
        self._key = access_key.strip()

    async def collect(
        self,
        *,
        reference_date: date | None = None,
        keywords: tuple[str, ...] | None = None,
    ) -> tuple[list[PeopleCollectDto], dict[str, int]]:
        target_date = reference_date or date.today()
        kws = keywords or _DEFAULT_KEYWORDS
        stats = {"requests_total": 0, "requests_ok": 0, "errors": 0, "fetched": 0}
        rows: list[PeopleCollectDto] = []
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for kw in kws:
                stats["requests_total"] += 1
                params = {
                    "access-key": self._key,
                    "keywords": kw,
                    "count": "1",
                }
                headers = {"Accept": "application/json"}
                try:
                    async with session.get(_API_URL, params=params, headers=headers) as resp:
                        resp.raise_for_status()
                        payload = await resp.json(content_type=None)
                    total = parse_total(payload)
                    stats["requests_ok"] += 1
                except Exception:
                    stats["errors"] += 1
                    logger.exception("[saramin] 채용 수집 실패 keyword=%s", kw)
                    continue
                if total is None:
                    continue
                rows.append(
                    PeopleCollectDto(
                        source_type=_SOURCE_TYPE,
                        source_url=f"https://www.saramin.co.kr/zf_user/search?searchword={kw}",
                        keyword_or_job=kw[:100],
                        search_volume_or_count=total,
                        raw_metadata={"data_role": _DATA_ROLE},
                        reference_date=target_date,
                    )
                )
                await asyncio.sleep(0.15)  # 한도/429 방지
        stats["fetched"] = len(rows)
        return rows, stats


__all__ = ["SaraminRecruitCollector", "parse_total"]
