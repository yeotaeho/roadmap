# 영화진흥위원회(KOBIS) 일별 박스오피스 OpenAPI → raw_economic_data Bronze 수집 (콘텐츠 수요 신호)

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone

from domain.master.hub.services.collectors.economic.common.rss_wordpress_sync import (
    fetch_html_sync,
)
from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "KOBIS_BOXOFFICE_DAILY"
# 경제 축 섹터 매핑 코드 — pulse_repository._SECTOR_CODE_MAP['CONTENT_MEDIA']='content-creator'.
# 박스오피스는 콘텐츠 소비(수요) 신호다. 일별 기준일로 발행해 경제 축에 일별 밀도를 만든다.
_INDUSTRY_SECTOR = "CONTENT_MEDIA"
_BASE_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
)
_KST = timezone(timedelta(hours=9))


def _to_int(v: object) -> int | None:
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_daily_box_office(payload: dict, target_date: date) -> list[EconomicCollectDto]:
    """KOBIS 일별 박스오피스 JSON → EconomicCollectDto 목록(순수 함수·테스트 가능).

    각 영화 1행을 콘텐츠 섹터(CONTENT_MEDIA) 경제 신호로 변환한다.
    published_at = target_date(박스오피스 기준일)로 두어 경제 축의 일별 밀도를 만든다.
    """
    result = (payload or {}).get("boxOfficeResult", {}) or {}
    movies = result.get("dailyBoxOfficeList", []) or []
    pub = datetime(target_date.year, target_date.month, target_date.day, tzinfo=_KST)
    ymd = target_date.strftime("%Y%m%d")

    out: list[EconomicCollectDto] = []
    for m in movies:
        movie_cd = (m.get("movieCd") or "").strip()
        movie_nm = (m.get("movieNm") or "").strip()
        if not movie_cd or not movie_nm:
            continue
        rank = m.get("rank") or "-"
        audi_cnt = _to_int(m.get("audiCnt"))
        sales_amt = _to_int(m.get("salesAmt"))

        title = f"[박스오피스 {ymd} {rank}위] {movie_nm}"
        if audi_cnt is not None:
            title += f" (관객 {audi_cnt:,}명)"

        out.append(
            EconomicCollectDto(
                source_type=_SOURCE_TYPE,
                # (movie_cd, 기준일) 합성 — 동일 영화의 일자별 행을 dedup 가능하게 분리.
                source_url=(
                    "https://www.kobis.or.kr/kobis/business/mast/mvie/searchMovieInfo.do"
                    f"?code={movie_cd}&boDt={ymd}"
                ),
                raw_title=title[:500],
                investor_name=None,
                target_company_or_fund=movie_nm[:255],
                investment_amount=sales_amt,  # 일 매출(원) — 콘텐츠 수요 강도
                currency="KRW",
                raw_metadata={
                    "industry_sector": _INDUSTRY_SECTOR,  # 경제 축 → content-creator
                    "data_provider": "kobis",
                    "target_date": ymd,
                    "rank": _to_int(rank),
                    "movie_cd": movie_cd,
                    "movie_nm": movie_nm,
                    "audience_count": audi_cnt,
                    "sales_amount": sales_amt,
                    "audience_acc": _to_int(m.get("audiAcc")),
                    "sales_acc": _to_int(m.get("salesAcc")),
                    "open_date": (m.get("openDt") or None),
                },
                published_at=pub,
            )
        )
    return out


class KobisBoxOfficeCollector:
    """KOBIS 일별 박스오피스 수집 — 콘텐츠 섹터의 일별 소비(수요) 신호."""

    def __init__(self, api_key: str, *, inter_day_sleep_sec: float = 0.3):
        self._key = api_key
        self._sleep = inter_day_sleep_sec

    def _fetch_one(self, target_date: date) -> list[EconomicCollectDto]:
        ymd = target_date.strftime("%Y%m%d")
        url = f"{_BASE_URL}?key={self._key}&targetDt={ymd}"
        raw = fetch_html_sync(url, tag="kobis-boxoffice")
        if not raw:
            logger.warning("[kobis] fetch 빈 결과 targetDt=%s", ymd)
            return []
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            logger.warning("[kobis] JSON 파싱 실패 targetDt=%s", ymd)
            return []
        # KOBIS 오류 응답은 {"faultInfo": {...}} 형태.
        if isinstance(payload, dict) and "faultInfo" in payload:
            logger.warning("[kobis] API 오류 targetDt=%s: %s", ymd, payload.get("faultInfo"))
            return []
        return parse_daily_box_office(payload, target_date)

    def collect_sync(
        self, *, days_back: int = 1, end_date: date | None = None
    ) -> list[EconomicCollectDto]:
        """end_date(기본 어제)부터 과거로 days_back일의 일별 박스오피스를 수집.

        KOBIS는 당일 데이터를 익일 제공하므로 종료일 기본값을 어제로 둔다.
        초기 backfill 은 days_back 을 크게 주어 과거 일자를 누적한다(source_url 멱등).
        """
        end = end_date or (datetime.now(_KST).date() - timedelta(days=1))
        out: list[EconomicCollectDto] = []
        for i in range(max(1, days_back)):
            if i > 0 and self._sleep > 0:
                time.sleep(self._sleep)
            out.extend(self._fetch_one(end - timedelta(days=i)))
        return out

    async def collect(
        self, *, days_back: int = 1, end_date: date | None = None
    ) -> list[EconomicCollectDto]:
        return await asyncio.to_thread(
            lambda: self.collect_sync(days_back=days_back, end_date=end_date)
        )


__all__ = ["KobisBoxOfficeCollector", "parse_daily_box_office"]
