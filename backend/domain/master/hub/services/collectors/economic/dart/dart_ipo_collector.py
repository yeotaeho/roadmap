"""DART 발행공시(pblntf_ty=C) 기반 IPO·공모 선행 신호 컬렉터.

수집 대상:
  - 증권신고서(주식)       — 신주 모집 = IPO / 유상증자 선행 신호
  - 소액공모공시서류       — 소규모 IPO
  - 증권신고서(혼합증권)   — 전환사채·신주인수권 등 주식 관련

증권신고서 접수 → 금감원 심사 → 청약 → 상장 순서이므로,
접수일 기준 2~3개월 내 상장 예정 기업의 선행 지표로 활용 가능.

watermark: rcept_dt (YYYYMMDD) 증분 수집
날짜 범위: API 제한으로 단일 쿼리 최대 14일. 그 이상은 분할 불필요 (일별 수집).
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
_SOURCE_TYPE = "DART_IPO_DISCLOSURE"

# 발행공시(C) 중 주식 관련 = IPO 선행 신호
# DART 실제 보고서명: "주식" 아닌 "지분증권" 사용
_IPO_KEYWORDS = (
    "증권신고서(지분증권)",    # 신주 공모 = IPO / 유상증자 핵심 문서
    "소액공모",               # 소액공모공시서류, 소액공모실적보고서
    "증권신고서(혼합증권)",    # 전환사채+신주인수권 등 주식 연계
)

# 자본조달(채권·ABS·파생) 제외 — 주식 흐름이 아님
_EXCLUDE_KEYWORDS = (
    "채무증권",
    "자산유동화",
    "파생결합",
    "주가연계",
)


@dataclass(frozen=True)
class DartIpoWatermark:
    last_rcept_dt: str | None = None  # YYYYMMDD


def _parse_rcept_dt(s: str | None) -> datetime | None:
    if not s or len(s) < 8:
        return None
    try:
        return datetime.strptime(s[:8], "%Y%m%d").replace(tzinfo=_KST)
    except ValueError:
        return None


def _is_ipo_related(report_nm: str) -> bool:
    nm = report_nm or ""
    if any(ex in nm for ex in _EXCLUDE_KEYWORDS):
        return False
    return any(kw in nm for kw in _IPO_KEYWORDS)


class DartIpoCollector:
    """DART 발행공시(C)에서 주식 관련 증권신고서 수집."""

    def __init__(self, dart_api_key: str) -> None:
        self._key = dart_api_key

    async def collect(
        self,
        *,
        bgn_de: str,
        end_de: str,
        watermark: DartIpoWatermark | None = None,
        max_pages: int = 10,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        """발행공시(pblntf_ty=C)에서 IPO 관련 공시 수집.

        Args:
            bgn_de: 시작일 YYYYMMDD
            end_de: 종료일 YYYYMMDD (범위 14일 이하 권장)
            watermark: 직전 실행 watermark
            max_pages: API 페이지 상한
        """
        stats: dict[str, int] = {
            "pages_fetched": 0,
            "total_c_type": 0,
            "ipo_found": 0,
            "skipped_watermark": 0,
        }
        prev_dt = watermark.last_rcept_dt if watermark else None
        items: list[dict[str, Any]] = []

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession() as session:
            for page in range(1, max_pages + 1):
                params = {
                    "crtfc_key": self._key,
                    "pblntf_ty": "C",
                    "bgn_de": bgn_de,
                    "end_de": end_de,
                    "page_no": page,
                    "page_count": 100,
                }
                try:
                    async with session.get(_DART_LIST_URL, params=params, timeout=timeout) as r:
                        data = await r.json()
                except Exception as exc:
                    logger.warning("[dart_ipo] DART 요청 실패 page=%s: %s", page, exc)
                    break

                if data.get("status") != "000":
                    logger.warning("[dart_ipo] DART status=%s msg=%s", data.get("status"), data.get("message", ""))
                    break

                page_items = data.get("list") or []
                if not page_items:
                    break

                stats["pages_fetched"] += 1
                stop = False

                for item in page_items:
                    stats["total_c_type"] += 1
                    rcept_dt = item.get("rcept_dt", "") or ""

                    if prev_dt and rcept_dt and rcept_dt < prev_dt:
                        stats["skipped_watermark"] += 1
                        stop = True
                        break

                    if not _is_ipo_related(item.get("report_nm", "") or ""):
                        continue

                    stats["ipo_found"] += 1
                    items.append(item)

                if stop:
                    break

                total = data.get("total_count") or 0
                if page * 100 >= int(total):
                    break

        dtos = [self._to_dto(item) for item in items]
        logger.info(
            "[dart_ipo] pages=%s total_c=%s ipo=%s skip=%s → dtos=%s",
            stats["pages_fetched"], stats["total_c_type"],
            stats["ipo_found"], stats["skipped_watermark"], len(dtos),
        )
        return dtos, stats

    @staticmethod
    def _to_dto(item: dict[str, Any]) -> EconomicCollectDto:
        rcept_no = item.get("rcept_no") or ""
        corp_name = item.get("corp_name") or ""
        report_nm = item.get("report_nm") or ""
        rcept_dt = item.get("rcept_dt") or ""

        source_url = f"{_DART_VIEWER_URL}?rcpNo={rcept_no}" if rcept_no else None
        pub_at = _parse_rcept_dt(rcept_dt)

        return EconomicCollectDto(
            source_type=_SOURCE_TYPE,
            source_url=source_url,
            raw_title=f"[IPO공시] {corp_name} {report_nm}"[:500],
            investor_name=None,
            target_company_or_fund=corp_name or None,
            investment_amount=None,
            currency="KRW",
            raw_metadata={
                "rcept_no": rcept_no,
                "corp_code": item.get("corp_code"),
                "corp_cls": item.get("corp_cls"),
                "report_nm": report_nm,
                "rcept_dt": rcept_dt,
                "flr_nm": item.get("flr_nm"),
                "data_role": "IPO_SIGNAL",
                "industry_sector": "CAPITAL_MARKET",
                "collected_via": "dart-ipo-disclosure",
            },
            published_at=pub_at,
        )


__all__ = ["DartIpoCollector", "DartIpoWatermark", "_is_ipo_related", "_parse_rcept_dt"]
