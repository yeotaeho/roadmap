"""국민연금공단 주식 대량보유 공시 컬렉터 (DART 지분공시 pblntf_ty=D).

수집 대상:
  DART /api/list.json?pblntf_ty=D → flr_nm='국민연금공단' 필터

국민연금은 주식을 5% 이상 보유·변동 시 DART에 대량보유보고서를 제출하므로,
이를 통해 대형 기관 자금 흐름(어떤 섹터·기업에 진입/이탈하는지)을 파악할 수 있다.

watermark: 마지막 수집 rcept_dt (YYYYMMDD, 높을수록 최신)
  - 이전 실행에서 본 최대 날짜 이전은 건너뜀
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

_DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
_DART_VIEWER_URL = "https://dart.fss.or.kr/dsaf001/main.do"
_KST = timezone(timedelta(hours=9))
_SOURCE_TYPE = "NPS_PORTFOLIO_DART"
_INVESTOR_NAME = "국민연금공단"

# 대량보유보고서만 선별 (임원·주요주주 소유현황은 너무 많고 노이즈)
_BULK_HOLD_KEYWORDS = ("주식등의대량보유상황보고서",)


@dataclass(frozen=True)
class NpsWatermark:
    last_rcept_dt: str | None = None  # YYYYMMDD


def _parse_rcept_dt(s: str | None) -> datetime | None:
    if not s or len(s) < 8:
        return None
    try:
        return datetime.strptime(s[:8], "%Y%m%d").replace(tzinfo=_KST)
    except ValueError:
        return None


def _is_bulk_holding(report_nm: str) -> bool:
    return any(kw in (report_nm or "") for kw in _BULK_HOLD_KEYWORDS)


class NpsDartCollector:
    """DART 지분공시에서 국민연금공단 대량보유 변동 이력 수집."""

    def __init__(self, dart_api_key: str) -> None:
        self._key = dart_api_key

    async def collect(
        self,
        *,
        bgn_de: str,
        end_de: str,
        watermark: NpsWatermark | None = None,
        max_pages: int = 20,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        """pblntf_ty=D 지분공시에서 국민연금공단 대량보유 보고서 수집.

        Args:
            bgn_de: 시작일 YYYYMMDD
            end_de: 종료일 YYYYMMDD
            watermark: 직전 실행 watermark (last_rcept_dt 이하는 skip)
            max_pages: 페이지 상한

        Returns:
            (dtos, stats)
        """
        stats: dict[str, int] = {
            "pages_fetched": 0,
            "total_d_type": 0,
            "nps_found": 0,
            "bulk_hold": 0,
            "skipped_watermark": 0,
        }
        prev_dt = watermark.last_rcept_dt if watermark else None
        items: list[dict[str, Any]] = []

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession() as session:
            for page in range(1, max_pages + 1):
                params = {
                    "crtfc_key": self._key,
                    "pblntf_ty": "D",
                    "bgn_de": bgn_de,
                    "end_de": end_de,
                    "page_no": page,
                    "page_count": 100,
                }
                try:
                    async with session.get(_DART_LIST_URL, params=params, timeout=timeout) as r:
                        data = await r.json()
                except Exception as exc:
                    logger.warning("[nps_dart] DART 요청 실패 page=%s: %s", page, exc)
                    break

                if data.get("status") != "000":
                    logger.warning("[nps_dart] DART status=%s msg=%s", data.get("status"), data.get("message", ""))
                    break

                page_items = data.get("list") or []
                if not page_items:
                    break

                stats["pages_fetched"] += 1
                stop = False

                for item in page_items:
                    stats["total_d_type"] += 1
                    rcept_dt = item.get("rcept_dt", "") or ""

                    # watermark 도달 → 이후 항목은 이미 수집됨
                    if prev_dt and rcept_dt and rcept_dt < prev_dt:
                        stats["skipped_watermark"] += 1
                        stop = True
                        break

                    flr = item.get("flr_nm") or ""
                    if _INVESTOR_NAME not in flr:
                        continue

                    stats["nps_found"] += 1
                    report_nm = item.get("report_nm") or ""
                    if not _is_bulk_holding(report_nm):
                        continue

                    stats["bulk_hold"] += 1
                    items.append(item)

                if stop:
                    break

                # 마지막 페이지 도달
                total = data.get("total_count") or 0
                if page * 100 >= int(total):
                    break

        dtos = [self._to_dto(item) for item in items]
        logger.info(
            "[nps_dart] pages=%s total_d=%s nps=%s bulk=%s skip=%s → dtos=%s",
            stats["pages_fetched"], stats["total_d_type"], stats["nps_found"],
            stats["bulk_hold"], stats["skipped_watermark"], len(dtos),
        )
        return dtos, stats

    @staticmethod
    def _to_dto(item: dict[str, Any]) -> EconomicCollectDto:
        rcept_no = item.get("rcept_no") or ""
        corp_name = item.get("corp_name") or ""
        report_nm = item.get("report_nm") or ""
        rcept_dt = item.get("rcept_dt") or ""
        corp_code = item.get("corp_code") or ""

        source_url = f"{_DART_VIEWER_URL}?rcpNo={rcept_no}" if rcept_no else None
        pub_at = _parse_rcept_dt(rcept_dt)

        return EconomicCollectDto(
            source_type=_SOURCE_TYPE,
            source_url=source_url,
            raw_title=f"[국민연금] {corp_name} {report_nm}"[:500],
            investor_name=_INVESTOR_NAME,
            target_company_or_fund=corp_name or None,
            investment_amount=None,
            currency="KRW",
            raw_metadata={
                "rcept_no": rcept_no,
                "corp_code": corp_code,
                "corp_cls": item.get("corp_cls"),
                "report_nm": report_nm,
                "rcept_dt": rcept_dt,
                "data_role": "INSTITUTIONAL_PORTFOLIO",
                "industry_sector": "CAPITAL_FLOW",
                "collected_via": "dart-nps-bulk-holding",
            },
            published_at=pub_at,
        )


__all__ = ["NpsDartCollector", "NpsWatermark", "_is_bulk_holding", "_parse_rcept_dt"]
