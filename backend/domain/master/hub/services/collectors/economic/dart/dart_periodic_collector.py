"""DART 정기공시(A) 컬렉터 — 사업보고서·반기보고서 R&D/CAPEX 선행 신호.

전략 (ECONOMIC_FLOW_IMPLEMENTATION_ROADMAP.md §4.3):
  - pblntf_ty=A: 사업보고서(A001) / 반기보고서(A002) 수집
  - dart_fss 라이브러리 스레드 오프로딩 (기존 DartEconomicCollector 패턴 동일)
  - R&D/CAPEX 금액 추출: fnlttSinglAcntAll.json 1회 호출 후 Python sj_div 필터
    - sj_div 파라미터는 DART API에서 무시되므로 전체 계정을 받아 Python에서 분리
  - source_type: DART_PERIODIC_ANNUAL(사업보고서) / DART_PERIODIC_SEMIANNUAL(반기)
  - 상세 API 동시성: 5 (DART API 분당 제한 보호)

R&D 계정 키워드: 연구개발, 연구비, 개발비 (IS/CIS 계정 — 성질별 분류 기업만 추출 가능)
CAPEX 계정 키워드: 유형자산취득, 유형자산의취득 (CF 계정 — 음수=지출, abs 저장)

한계: 삼성·SK 등 기능별 분류 대기업은 R&D가 XBRL IS에 별도 항목 없음 → R&D=None 정상
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

import dart_fss as dart
import httpx

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))
_DART_BASE = "https://opendart.fss.or.kr/api"
_DETAIL_CONCURRENCY = 5

# 정기공시 보고서명 → source_type
_PERIODIC_REPORT_TYPES: tuple[tuple[str, str], ...] = (
    ("사업보고서",   "DART_PERIODIC_ANNUAL"),
    ("반기보고서",   "DART_PERIODIC_SEMIANNUAL"),
    ("분기보고서",   "DART_PERIODIC_QUARTERLY"),
)
# 수집 대상 보고서명 (이 중 하나를 포함해야 채택)
_TARGET_REPORT_KEYWORDS: tuple[str, ...] = ("사업보고서", "반기보고서")

# reprt_code 매핑 (fnlttSinglAcntAll 호출 시 필요)
_REPRT_CODE: dict[str, str] = {
    "사업보고서":   "11011",
    "반기보고서":   "11012",
    "분기보고서":   "11013",
}

# R&D 추출 키워드 (IS: 손익계산서)
_RND_KEYWORDS: tuple[str, ...] = ("연구개발", "연구비", "개발비")
# CAPEX 추출 키워드 (CF: 현금흐름표)
_CAPEX_KEYWORDS: tuple[str, ...] = ("유형자산취득", "유형자산의취득", "설비투자")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _published_at(rcept_dt: str | None) -> datetime | None:
    if not rcept_dt or len(rcept_dt) != 8:
        return None
    try:
        return datetime.strptime(rcept_dt, "%Y%m%d").replace(tzinfo=_KST)
    except ValueError:
        return None


def _classify_source_type(report_nm: str) -> str:
    for keyword, stype in _PERIODIC_REPORT_TYPES:
        if keyword in report_nm:
            return stype
    return "DART_PERIODIC_ANNUAL"


def _get_reprt_code(report_nm: str) -> str:
    for keyword, code in _REPRT_CODE.items():
        if keyword in report_nm:
            return code
    return "11011"


def _bsns_year_from_report(report_nm: str, rcept_dt: str) -> str | None:
    """사업보고서는 전년도 실적. 접수일 연도 - 1 (1분기 파일은 당해 연도)."""
    if not rcept_dt or len(rcept_dt) < 4:
        return None
    year = int(rcept_dt[:4])
    if "사업보고서" in report_nm:
        return str(year - 1)
    # 반기보고서: 당해 연도
    return str(year)


def _to_int(raw: Any) -> int | None:
    if raw is None:
        return None
    s = str(raw).replace(",", "").strip()
    if not s or s in ("-", ""):
        return None
    try:
        v = int(float(s))
        return abs(v) if v else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# financial enrichment (fnlttSinglAcntAll)
# ---------------------------------------------------------------------------


async def _fetch_all_accounts(
    client: httpx.AsyncClient,
    api_key: str,
    corp_code: str,
    bsns_year: str,
    reprt_code: str,
) -> list[dict[str, Any]]:
    """fnlttSinglAcntAll — OFS 전체 계정 1회 조회 (sj_div 파라미터는 API에서 무시됨)."""
    url = f"{_DART_BASE}/fnlttSinglAcntAll.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
        "fs_div": "OFS",
    }
    try:
        resp = await client.get(url, params=params, timeout=20)
        data = resp.json()
        if data.get("status") != "000":
            return []
        return data.get("list") or []
    except Exception:
        logger.debug("fnlttSinglAcntAll 실패 corp=%s year=%s", corp_code, bsns_year)
        return []


def _extract_rnd_amount(accounts: list[dict[str, Any]]) -> int | None:
    """IS/CIS 계정에서 연구개발비 합산 (성질별 분류 기업만 추출 가능)."""
    total = 0
    found = False
    for acc in accounts:
        if acc.get("sj_div") not in ("IS", "CIS"):
            continue
        nm = (acc.get("account_nm") or "").replace(" ", "")
        if any(kw in nm for kw in _RND_KEYWORDS):
            v = _to_int(acc.get("thstrm_amount"))
            if v:
                total += v
                found = True
    return total if found else None


def _extract_capex_amount(accounts: list[dict[str, Any]]) -> int | None:
    """CF 계정에서 유형자산취득 절댓값 합산."""
    total = 0
    found = False
    for acc in accounts:
        if acc.get("sj_div") != "CF":
            continue
        nm = (acc.get("account_nm") or "").replace(" ", "")
        if any(kw in nm for kw in _CAPEX_KEYWORDS):
            v = _to_int(acc.get("thstrm_amount"))
            if v:
                total += v
                found = True
    return total if found else None


# ---------------------------------------------------------------------------
# collector
# ---------------------------------------------------------------------------


class DartPeriodicCollector:
    """DART 정기공시(A) — 사업보고서·반기보고서 목록 + R&D/CAPEX 재무 보강.

    기존 DartEconomicCollector 와 동일하게 `dart_fss` 를 동기 스레드 오프로딩으로 실행한다.
    """

    def __init__(self, api_key: str):
        if not api_key or not api_key.strip():
            raise ValueError("DART API 키가 비어 있습니다.")
        self._api_key = api_key.strip()

    def _collect_list_sync(
        self,
        begin: str,
        end: str,
        page_count: int = 100,
    ) -> list[dict[str, Any]]:
        """dart.search(pblntf_ty=A) 전 페이지 순회 → raw dict 목록."""
        dart.set_api_key(self._api_key)
        out: list[dict[str, Any]] = []
        page_no = 1
        while True:
            try:
                res = dart.search(
                    bgn_de=begin,
                    end_de=end,
                    pblntf_ty="A",
                    page_no=page_no,
                    page_count=min(page_count, 100),
                    last_reprt_at="Y",
                )
            except Exception:
                logger.exception("DART 정기공시 목록 조회 실패 page=%s", page_no)
                break

            for rpt in res.report_list:
                nm = (getattr(rpt, "report_nm", "") or "").strip()
                if not any(kw in nm for kw in _TARGET_REPORT_KEYWORDS):
                    continue
                rcp = (
                    getattr(rpt, "rcp_no", None)
                    or getattr(rpt, "rcept_no", None)
                )
                if not rcp:
                    continue
                corp_code = (getattr(rpt, "corp_code", "") or "").strip()
                corp_nm = (getattr(rpt, "corp_name", "") or "").strip()
                rcept_raw = getattr(rpt, "rcept_dt", None)
                rcept_dt = (
                    str(rcept_raw).strip()[:8]
                    if rcept_raw is not None
                    else ""
                )
                out.append(
                    {
                        "rcept_no": str(rcp),
                        "corp_code": corp_code,
                        "corp_name": corp_nm,
                        "report_nm": nm,
                        "rcept_dt": rcept_dt,
                        "corp_cls": (getattr(rpt, "corp_cls", "") or ""),
                    }
                )

            total_page = int(getattr(res, "total_page", None) or 1)
            if page_no >= total_page:
                break
            page_no += 1
        return out

    async def collect(
        self,
        bgn_de: str | None = None,
        end_de: str | None = None,
        *,
        enrich_financials: bool = True,
        max_enrich: int = 200,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        """정기공시 수집 → (옵션) 재무제표 R&D·CAPEX 보강.

        Args:
            bgn_de/end_de: 접수일 범위 YYYYMMDD (미입력 시 최근 30일).
            enrich_financials: True 면 fnlttSinglAcntAll 로 R&D·CAPEX 추출 시도.
            max_enrich: 재무 보강 대상 최대 건수 (API 제한 보호).
        """
        end = end_de or datetime.now(_KST).strftime("%Y%m%d")
        begin = bgn_de or (datetime.now(_KST) - timedelta(days=30)).strftime("%Y%m%d")

        raw_list = await asyncio.to_thread(self._collect_list_sync, begin, end)
        stats: dict[str, int] = {
            "fetched_list": len(raw_list),
            "enriched": 0,
            "rnd_found": 0,
            "capex_found": 0,
        }

        if not raw_list:
            return [], stats

        # 중복 rcept_no 제거
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for r in raw_list:
            if r["rcept_no"] not in seen:
                seen.add(r["rcept_no"])
                unique.append(r)

        # 재무 보강 (corp_code 있는 법인, 최대 max_enrich)
        # Y/K 대기업은 CAPEX 위주, E/N 소형법인은 R&D 추출 가능 → 전체 포함
        if enrich_financials:
            enrich_targets = [
                r for r in unique if r.get("corp_code")
            ][:max_enrich]
            enriched_map: dict[str, dict[str, int | None]] = {}
            if enrich_targets:
                enriched_map = await self._enrich_financials(enrich_targets)
                stats["enriched"] = len(enriched_map)
                stats["rnd_found"] = sum(
                    1 for v in enriched_map.values() if v.get("rnd") is not None
                )
                stats["capex_found"] = sum(
                    1 for v in enriched_map.values() if v.get("capex") is not None
                )
        else:
            enriched_map = {}

        dtos = [
            self._to_dto(r, enriched_map.get(r["rcept_no"]))
            for r in unique
            if r.get("rcept_no")
        ]
        logger.info("[dart_periodic] dtos=%s stats=%s", len(dtos), stats)
        return dtos, stats

    async def _enrich_financials(
        self,
        reports: list[dict[str, Any]],
    ) -> dict[str, dict[str, int | None]]:
        """rcept_no → {rnd, capex} 매핑."""
        sem = asyncio.Semaphore(_DETAIL_CONCURRENCY)
        results: dict[str, dict[str, int | None]] = {}

        async def process(rpt: dict[str, Any]) -> None:
            rcept_no = rpt["rcept_no"]
            corp_code = rpt["corp_code"]
            report_nm = rpt["report_nm"]
            rcept_dt = rpt["rcept_dt"]
            bsns_year = _bsns_year_from_report(report_nm, rcept_dt)
            reprt_code = _get_reprt_code(report_nm)
            if not bsns_year or not corp_code:
                return
            async with sem:
                all_accts = await _fetch_all_accounts(
                    client, self._api_key, corp_code, bsns_year, reprt_code
                )
            rnd = _extract_rnd_amount(all_accts)
            capex = _extract_capex_amount(all_accts)
            if rnd is not None or capex is not None:
                results[rcept_no] = {"rnd": rnd, "capex": capex}

        async with httpx.AsyncClient(timeout=30.0) as client:
            await asyncio.gather(*[process(r) for r in reports])
        return results

    def _to_dto(
        self,
        rpt: dict[str, Any],
        financials: dict[str, int | None] | None,
    ) -> EconomicCollectDto:
        rcept_no = rpt["rcept_no"]
        corp_nm = rpt["corp_name"]
        report_nm = rpt["report_nm"]
        rcept_dt = rpt["rcept_dt"]

        source_type = _classify_source_type(report_nm)
        pub_at = _published_at(rcept_dt)
        url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

        rnd = (financials or {}).get("rnd")
        capex = (financials or {}).get("capex")
        # investment_amount: R&D 우선, 없으면 CAPEX, 없으면 None
        amount = rnd if rnd is not None else capex

        bsns_year = _bsns_year_from_report(report_nm, rcept_dt)
        raw_metadata: dict[str, Any] = {
            "rcept_no": rcept_no,
            "rcept_dt": rcept_dt or None,
            "corp_code": rpt.get("corp_code") or None,
            "corp_cls": rpt.get("corp_cls") or None,
            "report_nm": report_nm,
            "bsns_year": bsns_year,
            "pblntf_ty": "A",
            "rnd_amount": rnd,
            "capex_amount": capex,
            "collected_via": "dart-periodic-api",
        }

        return EconomicCollectDto(
            source_type=source_type,
            source_url=url,
            raw_title=f"{corp_nm} {report_nm}"[:500],
            investor_name=corp_nm,
            target_company_or_fund=None,
            investment_amount=amount,
            currency="KRW",
            raw_metadata=raw_metadata,
            published_at=pub_at,
        )


__all__ = ["DartPeriodicCollector"]
