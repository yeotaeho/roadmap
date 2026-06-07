"""KIPRIS 특허 출원 트렌드 컬렉터 — 기술 분야별 주간 출원량으로 혁신 선행 신호 측정.

API: KIPRIS PLUS patUtiModInfoSearchSevice/getAdvancedSearch
인증: ServiceKey (대문자 S) 파라미터
날짜: applicationDate=YYYYMMDD~YYYYMMDD (틸다 구분)

활용:
  - 기술 키워드(AI·바이오·에너지 등)별 특허 출원 건수 주별 수집
  - 출원 급증 = 해당 분야 R&D 투자 선행 신호 (상용화 2~3년 전 지표)

수집 방식:
  - 각 키워드 × 주간 날짜 범위 → totalCount만 조회 (원문 불필요)
  - source_url = keyword + 주 시작일 → 주별 멱등성 보장
  - 월 1,000건 한도 → 키워드 20개 × 주 1회 = ~80건/월 (여유 충분)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

_KIPRIS_SEARCH_URL = "https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getAdvancedSearch"
_KST = timezone(timedelta(hours=9))
_SOURCE_TYPE = "PATENT_KIPRIS_TREND"

# 기술 분야별 트렌드 키워드 — 혁신 선행 지표로 활용
_TECH_KEYWORD_GROUPS: list[tuple[str, list[str]]] = [
    ("AI_ML", [
        "인공지능",
        "딥러닝",
        "생성형AI",
        "거대언어모델",
    ]),
    ("BIOHEALTH", [
        "유전자치료",
        "세포치료",
        "의료AI",
        "바이오의약품",
    ]),
    ("ENERGY_CLIMATE", [
        "수소에너지",
        "태양전지",
        "이차전지",
        "탄소포집",
    ]),
    ("SEMICONDUCTOR", [
        "반도체공정",
        "뉴로모픽",
        "양자컴퓨터",
    ]),
    ("MOBILITY", [
        "자율주행",
        "전기차배터리",
        "도심항공교통",
    ]),
    ("FINTECH", [
        "블록체인",
        "디지털화폐",
    ]),
]

# getAdvancedSearch 필수 Boolean 플래그
_BOOL_PARAMS = {
    "patent": "Y", "utility": "N",
    "register": "Y", "registerRejected": "Y", "makeRejected": "Y",
    "open": "Y", "openReject": "Y", "abandon": "Y",
    "registration": "Y", "lapse": "Y", "withdraw": "Y",
    "cancel": "Y", "destroy": "Y",
}


@dataclass(frozen=True)
class KiprisWatermark:
    last_week_start: str | None = None  # YYYYMMDD (주 시작일)


class KiprisPatentCollector:
    """KIPRIS 특허 검색 API로 기술 키워드별 주간 출원 건수 수집."""

    def __init__(self, service_key: str) -> None:
        self._key = service_key

    async def collect(
        self,
        *,
        watermark: KiprisWatermark | None = None,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        """현재 주(월~일) 출원량 수집. 이미 수집한 주는 skip.

        Returns:
            (dtos, stats)
        """
        kst_now = datetime.now(tz=_KST)
        # 이번 주 월요일
        week_start = kst_now - timedelta(days=kst_now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=6)

        week_start_str = week_start.strftime("%Y%m%d")
        week_end_str = week_end.strftime("%Y%m%d")

        stats: dict[str, int] = {
            "keywords_total": sum(len(kws) for _, kws in _TECH_KEYWORD_GROUPS),
            "fetched": 0,
            "skipped_week": 0,
            "errors": 0,
        }

        # 이번 주 이미 수집했으면 skip
        if watermark and watermark.last_week_start == week_start_str:
            stats["skipped_week"] = stats["keywords_total"]
            logger.info("[kipris] 이번 주(%s) 이미 수집됨 — skip", week_start_str)
            return [], stats

        date_range = f"{week_start_str}~{week_end_str}"
        dtos: list[EconomicCollectDto] = []

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession() as session:
            for group_name, keywords in _TECH_KEYWORD_GROUPS:
                for keyword in keywords:
                    try:
                        total, sample_apps = await self._fetch_patent_count(
                            session, keyword, date_range, timeout
                        )
                        if total is None:
                            stats["errors"] += 1
                            continue

                        dto = self._to_dto(keyword, group_name, total, sample_apps,
                                           week_start_str, week_end_str, week_start)
                        dtos.append(dto)
                        stats["fetched"] += 1
                        logger.debug("[kipris] %s/%s: %d건", group_name, keyword, total)
                    except Exception as exc:
                        logger.warning("[kipris] 키워드 오류 [%s]: %s", keyword, exc)
                        stats["errors"] += 1

                    # KIPRIS API rate limit 보호
                    await asyncio.sleep(0.15)

        logger.info(
            "[kipris] week=%s~%s fetched=%s errors=%s",
            week_start_str, week_end_str, stats["fetched"], stats["errors"],
        )
        return dtos, stats

    async def _fetch_patent_count(
        self,
        session: aiohttp.ClientSession,
        keyword: str,
        date_range: str,
        timeout: aiohttp.ClientTimeout,
    ) -> tuple[int, list[str]] | tuple[None, None]:
        """키워드 + 날짜 범위로 특허 출원 건수 조회."""
        params = {
            **_BOOL_PARAMS,
            "numOfRows": "3",
            "pageNo": "1",
            "inventionTitle": keyword,
            "applicationDate": date_range,
        }
        # ServiceKey는 requests 라이브러리처럼 raw URL에 삽입 필요 (인코딩 문제 회피)
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{_KIPRIS_SEARCH_URL}?ServiceKey={self._key}&{query}"

        try:
            async with session.get(url, timeout=timeout) as r:
                if r.status != 200:
                    logger.warning("[kipris] HTTP %s keyword=%r", r.status, keyword)
                    return None, None
                text = await r.text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.warning("[kipris] 요청 실패 keyword=%r: %s", keyword, exc)
            return None, None

        # XML 파싱 (정규식 경량 파싱 — lxml 의존성 최소화)
        import re
        code_m = re.search(r"<resultCode>(.*?)</resultCode>", text)
        code = code_m.group(1) if code_m else "?"
        if code != "00":
            logger.warning("[kipris] resultCode=%s keyword=%r", code, keyword)
            return None, None

        total_m = re.search(r"<totalCount>(.*?)</totalCount>", text)
        total = int(total_m.group(1)) if total_m else 0

        apps = re.findall(r"<applicationNumber>(.*?)</applicationNumber>", text)
        return total, apps[:3]

    @staticmethod
    def _to_dto(
        keyword: str,
        group_name: str,
        total: int,
        sample_apps: list[str],
        week_start_str: str,
        week_end_str: str,
        week_start_dt: datetime,
    ) -> EconomicCollectDto:
        import urllib.parse
        kw_enc = urllib.parse.quote(keyword)
        source_url = (
            f"https://plus.kipris.or.kr/search/patent"
            f"?query={kw_enc}&applicationDateFrom={week_start_str}&applicationDateTo={week_end_str}"
        )

        return EconomicCollectDto(
            source_type=_SOURCE_TYPE,
            source_url=source_url,
            raw_title=f"[{group_name}] {keyword} 특허 출원 {total}건 ({week_start_str[:6]}W)"[:500],
            investor_name=None,
            target_company_or_fund=None,
            investment_amount=None,
            currency="KRW",
            raw_metadata={
                "keyword": keyword,
                "group_name": group_name,
                "total_count": total,
                "week_start": week_start_str,
                "week_end": week_end_str,
                "sample_applications": sample_apps,
                "data_role": "PATENT_TREND_SIGNAL",
                "industry_sector": group_name,
                "collected_via": "kipris-plus-api",
            },
            published_at=week_start_dt,
        )


__all__ = [
    "KiprisPatentCollector",
    "KiprisWatermark",
    "_TECH_KEYWORD_GROUPS",
]
