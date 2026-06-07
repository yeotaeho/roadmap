"""네이버 DataLab 검색량 트렌드 컬렉터 — 분야별 주간 실제 검색 수요 측정.

API: POST https://openapi.naver.com/v1/datalab/search
인증: X-Naver-Client-Id / X-Naver-Client-Secret 헤더

  - 사용자가 실제 검색한 횟수 → 수요 선행 신호
  - 상대 비율(0~100, 최고점=100) → 동일 요청 내 분야 간 상대 비교
  - 핵심 7그룹(경제 5 + 청년 진로 2)을 배치 요청으로 수집
  - 최소 1주 단위 시계열 → Silver에서 모멘텀·가속도 계산 가능

수집 방식:
  - start_date~end_date 범위의 주별(timeUnit=week) 시계열 수집
  - 그룹 × 주 = 1 DTO → source_url UNIQUE로 멱등성 보장
  - watermark: last_week_start — 이미 수집된 주의 DTO skip (DB unique 중복 방지)
  - backfill: start_date를 과거로 지정하면 전체 기간 한번에 수집 가능
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

_DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
_KST = timezone(timedelta(hours=9))
_SOURCE_TYPE = "DISCOURSE_NAVER_DATALAB"
_BATCH_SIZE = 5  # API 최대 5그룹/요청

# 분야별 검색 트렌드 키워드 그룹 (그룹당 최대 5개 키워드, 합산 집계)
# API 최대 5그룹/요청 → 7그룹을 2배치(5+2)로 나눠 호출
# CAREER_SWITCH·GOV_SUPPORT 는 Roadmap 핵심 타깃(청년 진로) 수요 측정에 필수
_DATALAB_KEYWORD_GROUPS: list[tuple[str, list[str]]] = [
    ("AI_TECH",        ["인공지능", "AI", "생성형AI", "LLM", "GPT"]),
    ("STARTUP_VC",     ["스타트업", "벤처투자", "투자유치", "시리즈A"]),
    ("CAREER_SWITCH",  ["이직", "취업준비", "직업전환", "N잡"]),
    ("BIOHEALTH",      ["바이오", "헬스케어", "신약", "임상시험"]),
    ("ENERGY_CLIMATE", ["재생에너지", "수소에너지", "탄소중립", "전기차"]),
    ("FINTECH",        ["핀테크", "토큰증권", "디지털화폐", "블록체인"]),
    ("GOV_SUPPORT",    ["정부지원", "창업지원", "청년지원", "스타트업지원"]),
]


@dataclass(frozen=True)
class NaverDatalabWatermark:
    last_week_start: str | None = None  # YYYYMMDD (최신 수집 주 시작일)


class NaverDatalabCollector:
    """네이버 DataLab API로 분야별 주간 검색량 비율 수집."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._id = client_id
        self._secret = client_secret

    async def collect(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        watermark: NaverDatalabWatermark | None = None,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        """DataLab 주간 검색량 시계열 수집.

        Args:
            start_date: 조회 시작일 YYYYMMDD (기본: 오늘-28일)
            end_date:   조회 종료일 YYYYMMDD (기본: 오늘)
            watermark:  last_week_start 이전 주는 DTO 생성 skip (DB 중복 방지)

        Returns:
            (dtos, stats) — 그룹 × 주 단위 DTO 목록
        """
        kst_now = datetime.now(tz=_KST)
        end_dt = (
            datetime.strptime(end_date, "%Y%m%d").replace(tzinfo=_KST)
            if end_date
            else kst_now
        )
        start_dt = (
            datetime.strptime(start_date, "%Y%m%d").replace(tzinfo=_KST)
            if start_date
            else kst_now - timedelta(days=28)
        )

        # DataLab API는 YYYY-MM-DD 형식 요구
        api_start = start_dt.strftime("%Y-%m-%d")
        api_end = end_dt.strftime("%Y-%m-%d")

        stats: dict[str, int] = {
            "groups_total": len(_DATALAB_KEYWORD_GROUPS),
            "batches_fetched": 0,
            "dtos_created": 0,
            "dtos_skipped_watermark": 0,
            "errors": 0,
        }

        wm_last = watermark.last_week_start if watermark else None
        all_dtos: list[EconomicCollectDto] = []

        headers = {
            "X-Naver-Client-Id": self._id,
            "X-Naver-Client-Secret": self._secret,
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession() as session:
            # 5그룹씩 배치 요청
            groups = _DATALAB_KEYWORD_GROUPS
            for batch_start in range(0, len(groups), _BATCH_SIZE):
                batch = groups[batch_start : batch_start + _BATCH_SIZE]
                payload = {
                    "startDate": api_start,
                    "endDate": api_end,
                    "timeUnit": "week",
                    "keywordGroups": [
                        {"groupName": gname, "keywords": kws}
                        for gname, kws in batch
                    ],
                }
                try:
                    async with session.post(
                        _DATALAB_URL, headers=headers, json=payload, timeout=timeout
                    ) as r:
                        if r.status != 200:
                            body = await r.text()
                            logger.warning(
                                "[naver_datalab] HTTP %s batch=%d: %s",
                                r.status, batch_start, body[:200],
                            )
                            stats["errors"] += len(batch)
                            continue
                        data = await r.json()
                except Exception as exc:
                    logger.warning("[naver_datalab] 요청 실패 batch=%d: %s", batch_start, exc)
                    stats["errors"] += len(batch)
                    continue

                stats["batches_fetched"] += 1

                for result, (gname, kws) in zip(data.get("results", []), batch):
                    for pt in result.get("data", []):
                        period_str = pt.get("period", "")  # "YYYY-MM-DD"
                        ratio = pt.get("ratio")
                        if not period_str or ratio is None:
                            continue

                        # 주 시작일 YYYYMMDD 변환
                        week_start_str = period_str.replace("-", "")
                        week_start_dt = datetime.strptime(period_str, "%Y-%m-%d").replace(tzinfo=_KST)
                        week_end_str = (week_start_dt + timedelta(days=6)).strftime("%Y%m%d")

                        # watermark 이전 주 skip
                        if wm_last and week_start_str <= wm_last:
                            stats["dtos_skipped_watermark"] += 1
                            continue

                        dto = self._to_dto(
                            gname, kws, float(ratio),
                            week_start_str, week_end_str, week_start_dt,
                        )
                        all_dtos.append(dto)
                        stats["dtos_created"] += 1

                await asyncio.sleep(0.3)  # DataLab rate limit 보호

        logger.info(
            "[naver_datalab] start=%s end=%s batches=%s dtos=%s skip=%s errors=%s",
            api_start, api_end,
            stats["batches_fetched"], stats["dtos_created"],
            stats["dtos_skipped_watermark"], stats["errors"],
        )
        return all_dtos, stats

    @staticmethod
    def _to_dto(
        group_name: str,
        keywords: list[str],
        ratio: float,
        week_start_str: str,
        week_end_str: str,
        week_start_dt: datetime,
    ) -> EconomicCollectDto:
        # 그룹 + 주 단위 논리 URL → source_url UNIQUE 멱등성 보장
        source_url = (
            f"https://datalab.naver.com/keyword/trendResult.naver"
            f"?group={group_name}&weekStart={week_start_str}"
        )
        return EconomicCollectDto(
            source_type=_SOURCE_TYPE,
            source_url=source_url,
            raw_title=(
                f"[{group_name}] 네이버 검색 트렌드 ratio={ratio:.1f} "
                f"({week_start_str[:4]}-{week_start_str[4:6]}-{week_start_str[6:]}W)"
            )[:500],
            investor_name=None,
            target_company_or_fund=None,
            investment_amount=None,
            currency="KRW",
            raw_metadata={
                "group_name": group_name,
                "keywords": keywords,
                "ratio": ratio,
                "week_start": week_start_str,
                "week_end": week_end_str,
                "data_role": "SEARCH_TREND_SIGNAL",
                "industry_sector": group_name,
                "collected_via": "naver-datalab-api",
            },
            published_at=week_start_dt,
        )


__all__ = [
    "NaverDatalabCollector",
    "NaverDatalabWatermark",
    "_DATALAB_KEYWORD_GROUPS",
]
