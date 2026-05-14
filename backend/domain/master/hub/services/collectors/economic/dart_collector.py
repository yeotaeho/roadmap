"""DART Open API 기반 경제 Bronze 수집 — `dart-fss` (동기) + 스레드 오프로딩.

공시 카테고리(`pblntf_ty`):
  - A: 정기공시
  - B: **주요사항보고** — M&A · 타법인 출자/취득 · 시설투자 · 유상증자 등
  - C: 발행공시 (증권신고서 · 소액공모) — 기업이 본인 자본을 조달하는 공시이므로
        "자본의 흐름(누가 어디에 투자했는가)" 에는 부적합하여 제외.
  - D: **지분공시** — 대량보유·의결권 대량보유 등 (기관·대주주 지분 변동 시그널)
  - E~J: 기타 (미사용)

Phase 1 고도화 (2026-05-11):
  - 키워드 확장: 신규시설투자 등, 유상증자 등
  - source_type 세분화: DART_M_AND_A / DART_FACILITY_INVEST / DART_CAPITAL_INCREASE
  - published_at: 접수일 YYYYMMDD → 해당 일 00:00 KST (UTC+9, 고정 오프셋)

2026-05-12:
  - `pblntf_ty=D` 지분공시 병행 수집 (대량보유·의결권 대량보유 중심, 제목 키워드 필터)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

import dart_fss as dart
import httpx

from domain.master.hub.services.collectors.economic.dart_detail_fetcher import (
    DartDetailRoute,
    extract_amount,
    extract_target_name,
    fetch_detail,
    route_for_title,
)
from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

# 단일 보고서 상세 조회 동시성 한계 — DART API 분당 호출 제한 보호.
_DETAIL_FETCH_CONCURRENCY = 10

# DART 접수일은 한국 실무상 KST(UTC+9) 자정 기준으로 해석 (DB는 TIMESTAMPTZ로 +09:00 유지).
_KST = timezone(timedelta(hours=9))

# Phase 1: 키워드 확장. DART 공식 보고서명은 "양수/양도"를 사용 (≠ 우리가 흔히 쓰는 취득/처분).
# 두 표현 모두 매칭되도록 키워드를 병행 등록한다.
_REPORT_KEYWORDS = (
    # 타법인 지분 거래
    "타법인주식 및 출자증권 양수",
    "타법인주식 및 출자증권 양도",
    "타법인주식 및 출자증권 취득",
    "타법인주식 및 출자증권 처분",
    "타법인 주식",
    "출자증권 양수",
    "출자증권 양도",
    "출자증권 취득",
    "출자증권 처분",
    "주식교환",
    "주식이전",
    "회사합병",
    "회사분할합병",
    "회사분할",
    "영업양수",
    "영업양도",
    "유형자산 양수",
    "유형자산 양도",
    "자산양수",
    "자산양도",
    # 신규시설투자 (DART 표준: 유형자산 양수 결정으로 통합)
    "신규시설투자 등",
    "신규시설투자",
    "증설결정",
    # 유상증자 (자본 조달의 역방향 추적)
    "유상증자 결정",
    "제3자배정",
    # 전환사채(CB) — 채권 자금 조달
    "전환사채권 발행결정",
    "전환사채",
)

# 제목에 최초 매칭되는 규칙으로 source_type 결정 (길고 구체적인 키워드를 앞에 둔다).
_CLASSIFICATION_RULES: tuple[tuple[str, str], ...] = (
    ("신규시설투자 등", "DART_FACILITY_INVEST"),
    ("신규시설투자", "DART_FACILITY_INVEST"),
    ("증설결정", "DART_FACILITY_INVEST"),
    ("유형자산 양수", "DART_FACILITY_INVEST"),
    ("유형자산 양도", "DART_FACILITY_INVEST"),
    ("유상증자 결정", "DART_CAPITAL_INCREASE"),
    ("제3자배정", "DART_CAPITAL_INCREASE"),
    ("전환사채권 발행결정", "DART_CONVERTIBLE_BOND"),
    ("전환사채", "DART_CONVERTIBLE_BOND"),
    ("타법인주식 및 출자증권 양수", "DART_M_AND_A"),
    ("타법인주식 및 출자증권 양도", "DART_M_AND_A"),
    ("타법인주식 및 출자증권 취득", "DART_M_AND_A"),
    ("타법인주식 및 출자증권 처분", "DART_M_AND_A"),
    ("타법인 주식", "DART_M_AND_A"),
    ("출자증권 양수", "DART_M_AND_A"),
    ("출자증권 양도", "DART_M_AND_A"),
    ("출자증권 취득", "DART_M_AND_A"),
    ("출자증권 처분", "DART_M_AND_A"),
    ("주식교환", "DART_M_AND_A"),
    ("주식이전", "DART_M_AND_A"),
    ("회사분할합병", "DART_M_AND_A"),
    ("회사합병", "DART_M_AND_A"),
    ("회사분할", "DART_M_AND_A"),
    ("영업양수", "DART_M_AND_A"),
    ("영업양도", "DART_M_AND_A"),
    ("자산양수", "DART_M_AND_A"),
    ("자산양도", "DART_M_AND_A"),
)


def _classify_source_type(title: str) -> str:
    """공시 제목 기반 source_type 자동 분류."""
    for keyword, stype in _CLASSIFICATION_RULES:
        if keyword in title:
            return stype
    return "DART_MAJOR_SECURITIES_ACQUISITION"


# 지분공시(D): 자본 흐름의 역방향·포지션 변화 (기관/대주주)
_D_REPORT_KEYWORDS: tuple[str, ...] = (
    "대량보유상황보고",
    "주식등의 대량보유",
    "주식등의대량보유",
    "의결권대량보유",
    "의결권 대량보유",
)

_OWNERSHIP_CLASSIFICATION_RULES: tuple[tuple[str, str], ...] = (
    ("의결권대량보유", "DART_OWNERSHIP_VOTING_RIGHTS"),
    ("의결권 대량보유", "DART_OWNERSHIP_VOTING_RIGHTS"),
    ("주식등의 대량보유", "DART_OWNERSHIP_BULK"),
    ("주식등의대량보유", "DART_OWNERSHIP_BULK"),
    ("대량보유상황보고", "DART_OWNERSHIP_BULK"),
)

_DEFAULT_OWNERSHIP_SOURCE_TYPE = "DART_OWNERSHIP_DISCLOSURE"


def _classify_source_type_ownership(title: str) -> str:
    """지분공시(D) 제목 기반 source_type."""
    for keyword, stype in _OWNERSHIP_CLASSIFICATION_RULES:
        if keyword in title:
            return stype
    return _DEFAULT_OWNERSHIP_SOURCE_TYPE


def _published_at_kst_from_rcept_dt(rcept_dt: str | None) -> datetime | None:
    """YYYYMMDD 접수일을 해당 일자 00:00 KST(UTC+9) 로 해석해 TIMESTAMPTZ 로 저장."""
    if not rcept_dt or len(rcept_dt) != 8:
        return None
    try:
        return datetime.strptime(rcept_dt, "%Y%m%d").replace(tzinfo=_KST)
    except ValueError:
        return None


class DartEconomicCollector:
    """Open DART 공시 목록 API — 주요사항보고(B) + 지분공시(D), 제목 키워드 필터.

    운영 보완: 접수일 KST 자정 해석, source_type 규칙 기반 분류, 서비스 계층에서 수집 예외 격리.
    """

    def __init__(self, api_key: str):
        if not api_key or not api_key.strip():
            raise ValueError("DART API 키가 비어 있습니다. DART_API_KEY 또는 OPENDART_API_KEY 를 설정하세요.")
        self._api_key = api_key.strip()

    def _collect_pblntf_ty_sync(
        self,
        *,
        pblntf_ty: str,
        begin: str,
        end: str,
        title_keywords: Sequence[str],
        classify_source_type: Callable[[str], str],
        page_count: int,
        last_reprt_at: str = "Y",
    ) -> list[EconomicCollectDto]:
        """단일 공시 유형에 대해 페이지네이션 전체 순회."""
        out: list[EconomicCollectDto] = []
        page_no = 1

        while True:
            try:
                res = dart.search(
                    bgn_de=begin,
                    end_de=end,
                    pblntf_ty=pblntf_ty,
                    page_no=page_no,
                    page_count=min(page_count, 100),
                    last_reprt_at=last_reprt_at,
                )
            except Exception:
                logger.exception(
                    "DART dart.search 실패 (pblntf_ty=%s, page=%s)", pblntf_ty, page_no
                )
                raise

            for report in res.report_list:
                try:
                    title = getattr(report, "report_nm", "") or ""
                except AttributeError:
                    title = ""

                if not any(k in title for k in title_keywords):
                    continue

                try:
                    corp_name = getattr(report, "corp_name", "") or ""
                except AttributeError:
                    corp_name = ""

                rcp = getattr(report, "rcp_no", None) or getattr(report, "rcept_no", None)
                if not rcp:
                    continue

                rcept_raw = getattr(report, "rcept_dt", None)
                rcept_dt = (
                    rcept_raw.strip()
                    if isinstance(rcept_raw, str)
                    else (str(rcept_raw).strip() if rcept_raw is not None else "")
                )
                if len(rcept_dt) > 8 and rcept_dt[:8].isdigit():
                    rcept_dt = rcept_dt[:8]
                published_at = _published_at_kst_from_rcept_dt(rcept_dt if len(rcept_dt) == 8 else None)

                url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}"

                source_type = classify_source_type(title)

                raw_title = (title or "").strip()
                if not raw_title:
                    raw_title = f"공시_{rcp}"
                if len(raw_title) > 500:
                    raw_title = raw_title[:497] + "..."

                investor_name = (corp_name or "").strip() or None

                # 주요사항보고서 상세 API는 corp_code + bgn_de + end_de 가 필수이므로
                # 리스트 단계에서 raw_metadata 에 보존한다.
                try:
                    corp_code = getattr(report, "corp_code", None) or ""
                except AttributeError:
                    corp_code = ""

                raw_metadata: dict[str, Any] = {
                    "rcept_no": str(rcp),
                    "rcept_dt": rcept_dt if len(rcept_dt) == 8 else None,
                    "corp_code": (corp_code or "").strip() or None,
                    "report_nm": raw_title,
                    "pblntf_ty": pblntf_ty,
                }

                out.append(
                    EconomicCollectDto(
                        source_type=source_type,
                        source_url=url,
                        raw_title=raw_title,
                        investor_name=investor_name,
                        target_company_or_fund=None,
                        investment_amount=None,
                        published_at=published_at,
                        raw_metadata=raw_metadata,
                    )
                )

            total_page = int(getattr(res, "total_page", None) or 1)
            if page_no >= total_page:
                break
            page_no += 1

        return out

    def collect_sync(
        self,
        bgn_de: str | None = None,
        end_de: str | None = None,
        *,
        page_count: int = 100,
        include_ownership_disclosure: bool = True,
    ) -> list[EconomicCollectDto]:
        dart.set_api_key(self._api_key)

        end = end_de or datetime.now().strftime("%Y%m%d")
        begin = bgn_de or (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

        out = self._collect_pblntf_ty_sync(
            pblntf_ty="B",
            begin=begin,
            end=end,
            title_keywords=_REPORT_KEYWORDS,
            classify_source_type=_classify_source_type,
            page_count=page_count,
            last_reprt_at="Y",
        )
        n_b = len(out)

        if include_ownership_disclosure:
            out_d = self._collect_pblntf_ty_sync(
                pblntf_ty="D",
                begin=begin,
                end=end,
                title_keywords=_D_REPORT_KEYWORDS,
                classify_source_type=_classify_source_type_ownership,
                page_count=page_count,
                last_reprt_at="Y",
            )
            out.extend(out_d)
            n_d = len(out_d)
        else:
            n_d = 0

        # 동일 URL 중복 제거 (페이지 경계·B/D 간 중복 방지)
        seen: set[str] = set()
        unique: list[EconomicCollectDto] = []
        for dto in out:
            u = dto.source_url or ""
            if u in seen:
                continue
            seen.add(u)
            unique.append(dto)

        logger.info(
            "DART 수집 완료: 기간 %s~%s, 주요사항보고(B) 후보 %s건, 지분공시(D) 후보 %s건, URL 기준 유니크 %s건",
            begin,
            end,
            n_b,
            n_d,
            len(unique),
        )
        return unique

    async def collect(
        self,
        bgn_de: str | None = None,
        end_de: str | None = None,
        *,
        page_count: int = 100,
        include_ownership_disclosure: bool = True,
        enrich_details: bool = True,
    ) -> list[EconomicCollectDto]:
        """리스트 수집 → (옵션) 보고서 유형별 상세 조회로 금액·대상 정보 보강."""
        dtos = await asyncio.to_thread(
            lambda: self.collect_sync(
                bgn_de,
                end_de,
                page_count=page_count,
                include_ownership_disclosure=include_ownership_disclosure,
            )
        )
        if not enrich_details or not dtos:
            return dtos
        return await self._enrich_with_detail_api(dtos)

    async def _enrich_with_detail_api(
        self,
        dtos: list[EconomicCollectDto],
    ) -> list[EconomicCollectDto]:
        """제목 라우팅 + raw_metadata(corp_code, rcept_dt, rcept_no) 로 상세 API 호출."""
        tasks: list[tuple[int, DartDetailRoute, str, str, str]] = []
        for idx, dto in enumerate(dtos):
            route = route_for_title(dto.raw_title or "")
            if route is None:
                continue
            meta = dto.raw_metadata or {}
            rcept_no = str(meta.get("rcept_no") or "").strip()
            corp_code = str(meta.get("corp_code") or "").strip()
            rcept_dt = str(meta.get("rcept_dt") or "").strip()
            if not (rcept_no and corp_code and rcept_dt and len(rcept_dt) == 8):
                continue
            tasks.append((idx, route, rcept_no, corp_code, rcept_dt))

        if not tasks:
            logger.info("DART 상세 조회 대상 0건 (라우팅·메타 미충족) — 보강 스킵")
            return dtos

        sem = asyncio.Semaphore(_DETAIL_FETCH_CONCURRENCY)
        async with httpx.AsyncClient(timeout=30.0) as client:
            async def _bounded_fetch(
                idx: int,
                route: DartDetailRoute,
                rcept: str,
                corp: str,
                dt: str,
            ) -> tuple[int, DartDetailRoute, dict | None]:
                async with sem:
                    detail = await fetch_detail(
                        client,
                        self._api_key,
                        route.endpoint,
                        rcept_no=rcept,
                        corp_code=corp,
                        rcept_dt=dt,
                    )
                return idx, route, detail

            results = await asyncio.gather(
                *(_bounded_fetch(i, r, rc, cc, dt) for (i, r, rc, cc, dt) in tasks),
                return_exceptions=True,
            )

        enriched_count = 0
        amount_filled = 0
        for res in results:
            if isinstance(res, BaseException):
                logger.debug("DART 상세 조회 예외: %s", res)
                continue
            idx, route, detail = res
            if not detail:
                continue
            dtos[idx] = _merge_detail_into_dto(dtos[idx], detail, route)
            enriched_count += 1
            if dtos[idx].investment_amount is not None:
                amount_filled += 1

        logger.info(
            "DART 상세 조회 보강 완료: 대상=%s, 응답=%s, 금액채움=%s",
            len(tasks),
            enriched_count,
            amount_filled,
        )
        return dtos


def _merge_detail_into_dto(
    dto: EconomicCollectDto,
    detail: dict[str, Any],
    route: DartDetailRoute,
) -> EconomicCollectDto:
    """상세 응답을 DTO 에 병합 (immutable 복제). 금액·대상명·raw_metadata 채움."""
    amount = extract_amount(detail, route.amount_fields)
    target = extract_target_name(detail)

    merged_meta: dict[str, Any] = dict(dto.raw_metadata or {})
    merged_meta.update(
        {
            "dart_detail_endpoint": route.endpoint,
            "dart_detail_label": route.label,
            "dart_detail": detail,
        }
    )

    return dto.model_copy(
        update={
            "investment_amount": amount if amount is not None else dto.investment_amount,
            "target_company_or_fund": target
            if target is not None
            else dto.target_company_or_fund,
            "raw_metadata": merged_meta,
        }
    )
