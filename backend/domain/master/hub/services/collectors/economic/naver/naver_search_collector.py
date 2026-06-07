"""네이버 뉴스 기사 수 컬렉터 — 키워드별 일별 언론 보도량(공급) 측정.

API: GET https://openapi.naver.com/v1/search/news.json
인증: X-Naver-Client-Id / X-Naver-Client-Secret 헤더

  - 언론이 특정 키워드를 얼마나 다루는지 → 공급(supply) 측 신호
  - DataLab 검색량(수요)과 교차 분석 → "뉴스 급증 → 검색 급증" 패턴 포착
  - 키워드별 일별 기사 total 수집 → Silver 에서 모멘텀·가속도 계산 가능

수집 방식:
  - 그룹별 각 키워드를 date 범위(ds/de)로 개별 조회 → total 값 수집
  - 그룹 × 키워드 × 날짜 = 1 DTO → source_url UNIQUE 멱등성 보장
  - watermark: last_collected_date — 이미 수집한 날 DTO skip
  - 기본 수집일: 어제 (당일 기사 집계가 완료된 날 기준)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import aiohttp

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

_SEARCH_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
_KST = timezone(timedelta(hours=9))
_SOURCE_TYPE = "DISCOURSE_NAVER_NEWS"

# 7그룹 × 합계 24개 키워드
# CAREER_SWITCH·GOV_SUPPORT 는 Roadmap 플랫폼 핵심 타깃(청년 진로) 측정에 필수
_NEWS_KEYWORD_GROUPS: list[tuple[str, list[str]]] = [
    ("AI_ML",           ["인공지능", "AI", "생성형AI", "LLM"]),
    ("STARTUP_VC",      ["스타트업", "벤처투자", "투자유치"]),
    ("CAREER_SWITCH",   ["이직", "취업준비", "직업전환", "N잡"]),
    ("BIOHEALTH",       ["바이오", "헬스케어", "신약"]),
    ("ENERGY_CLIMATE",  ["재생에너지", "탄소중립", "수소에너지"]),
    ("FINTECH",         ["핀테크", "디지털화폐", "블록체인"]),
    ("GOV_SUPPORT",     ["정부지원", "창업지원", "청년지원", "스타트업지원"]),
]


@dataclass(frozen=True)
class NaverSearchWatermark:
    last_collected_date: str | None = None  # YYYYMMDD (최신 수집 날짜)


class NaverSearchCollector:
    """네이버 뉴스 검색 API로 키워드별 일별 기사 수(total) 수집."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._id = client_id
        self._secret = client_secret

    async def collect(
        self,
        *,
        target_date: str | None = None,
        watermark: NaverSearchWatermark | None = None,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        """키워드별 일별 뉴스 기사 수 수집.

        Args:
            target_date: 수집 날짜 YYYYMMDD (기본: 어제). 과거 날짜 지정 시 backfill 가능.
            watermark:   last_collected_date 이미 수집한 날 DTO skip.

        Returns:
            (dtos, stats) — 그룹 × 키워드 × 날짜 단위 DTO 목록
        """
        kst_now = datetime.now(tz=_KST)
        if target_date:
            target_dt = datetime.strptime(target_date, "%Y%m%d").replace(tzinfo=_KST)
        else:
            target_dt = (kst_now - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        date_str = target_dt.strftime("%Y%m%d")

        # watermark: 이미 수집된 날 skip
        if watermark and watermark.last_collected_date and date_str <= watermark.last_collected_date:
            logger.info(
                "[naver_search] watermark skip: date=%s last=%s",
                date_str,
                watermark.last_collected_date,
            )
            return [], {
                "date": date_str,
                "dtos_created": 0,
                "dtos_skipped_watermark": 1,
                "errors": 0,
            }

        # Naver News API: ds/de 는 YYYY.MM.DD 형식
        api_date = target_dt.strftime("%Y.%m.%d")

        stats: dict[str, int] = {
            "keywords_total": sum(len(kws) for _, kws in _NEWS_KEYWORD_GROUPS),
            "dtos_created": 0,
            "dtos_skipped_zero": 0,
            "errors": 0,
        }

        headers = {
            "X-Naver-Client-Id": self._id,
            "X-Naver-Client-Secret": self._secret,
        }
        timeout = aiohttp.ClientTimeout(total=10)
        all_dtos: list[EconomicCollectDto] = []

        async with aiohttp.ClientSession() as session:
            for group_name, keywords in _NEWS_KEYWORD_GROUPS:
                for keyword in keywords:
                    params: dict[str, Any] = {
                        "query": keyword,
                        "display": 1,
                        "start": 1,
                        "sort": "date",
                        "ds": api_date,
                        "de": api_date,
                    }
                    try:
                        async with session.get(
                            _SEARCH_NEWS_URL,
                            headers=headers,
                            params=params,
                            timeout=timeout,
                        ) as r:
                            if r.status != 200:
                                body = await r.text()
                                logger.warning(
                                    "[naver_search] HTTP %s kw=%s: %s",
                                    r.status, keyword, body[:200],
                                )
                                stats["errors"] += 1
                                continue
                            data = await r.json()
                    except Exception as exc:
                        logger.warning("[naver_search] 요청 실패 kw=%s: %s", keyword, exc)
                        stats["errors"] += 1
                        continue

                    total = data.get("total", 0)
                    dto = self._to_dto(group_name, keyword, total, date_str, target_dt)
                    all_dtos.append(dto)
                    stats["dtos_created"] += 1

                    await asyncio.sleep(0.1)  # Naver API rate limit 보호

        logger.info(
            "[naver_search] date=%s dtos=%s errors=%s",
            date_str,
            stats["dtos_created"],
            stats["errors"],
        )
        return all_dtos, stats

    @staticmethod
    def _to_dto(
        group_name: str,
        keyword: str,
        article_count: int,
        date_str: str,
        target_dt: datetime,
    ) -> EconomicCollectDto:
        # 키워드 + 날짜 기반 논리 URL → source_url UNIQUE 멱등성 보장
        encoded_kw = quote(keyword, safe="")
        fmt_date = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}"
        source_url = (
            f"https://search.naver.com/search.naver"
            f"?where=news&query={encoded_kw}&ds={fmt_date}&de={fmt_date}"
        )
        return EconomicCollectDto(
            source_type=_SOURCE_TYPE,
            source_url=source_url,
            raw_title=(
                f"[{group_name}][{keyword}] 네이버 뉴스 {article_count}건 ({date_str})"
            )[:500],
            investor_name=None,
            target_company_or_fund=None,
            investment_amount=None,
            currency="KRW",
            raw_metadata={
                "group_name": group_name,
                "keyword": keyword,
                "article_count": article_count,
                "date": date_str,
                "data_role": "NEWS_SUPPLY_SIGNAL",
                "industry_sector": group_name,
                "collected_via": "naver-search-news-api",
            },
            published_at=target_dt,
        )


__all__ = [
    "NaverSearchCollector",
    "NaverSearchWatermark",
    "_NEWS_KEYWORD_GROUPS",
]
