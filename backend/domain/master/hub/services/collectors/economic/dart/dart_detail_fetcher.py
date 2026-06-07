"""DART Open API 상세 조회(주요사항보고 본문 JSON) 페처.

리스트 API(`/api/list.json`)는 공시 메타정보만 제공하므로, 실제 "자본 흐름" 분석에
필요한 금액(원 단위)은 보고서 유형별 상세 API를 추가 호출해야 한다.

매핑된 5개 카테고리 (사용자 요청):
  1) 시설투자 (`nrcrfcInvDecsn`)
  2) 유상증자 (`piicDecsn`)
  3) 전환사채 발행 (`cvbdIsDecsn`)
  4) 타법인주식·출자증권 취득/처분 (`otrCprStkInvscrAcqsDecsn`, `otrCprStkInvscrTrfDecsn`)
  5) 합병·분할·교환·영업양수도 (`cmpMgDecsn`, `cmpDvDecsn`, `stkExtrDecsn`,
     `bsnInhDecsn`, `bsnTrfDecsn`, `astInhtrfDecsn`)

각 API 응답: `{"status":"000","message":"정상","list":[{...}]}` 형식 공통.
실제 필드명은 보고서 유형마다 다르므로, 다중 후보 필드를 우선순위로 시도해
"가장 큰 금액"을 추출한다.

source_type → endpoint 매핑은 `dart_collector._classify_source_type` 의 결과와 제목을
조합해 결정 (제목이 더 구체적이므로 1차 라우팅 키로 활용).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_DART_BASE = "https://opendart.fss.or.kr/api"


@dataclass(frozen=True)
class DartDetailRoute:
    """제목 키워드 → 상세 API 엔드포인트·금액 후보 필드 매핑."""

    endpoint: str
    amount_fields: tuple[str, ...]
    label: str


# DART 공식 OpenAPI 가이드 (DS005 주요사항보고서) 기준 엔드포인트·필드명.
# 제목 키워드 → 라우팅 (구체적 키워드가 앞쪽).
_TITLE_ROUTES: tuple[tuple[str, DartDetailRoute], ...] = (
    # 1) 시설투자(자본지출) — DART API 별도 endpoint 없음. "유형자산 양수 결정" 으로 포섭.
    #    https://opendart.fss.or.kr/api/tgastInhDecsn.json  (apiId=2020044)
    #    금액 필드: inhdtl_inhprc (양수내역(양수금액(원)))
    (
        "신규시설투자",
        DartDetailRoute(
            endpoint="tgastInhDecsn",
            amount_fields=("inhdtl_inhprc",),
            label="신규시설투자(유형자산 양수)",
        ),
    ),
    (
        "증설결정",
        DartDetailRoute(
            endpoint="tgastInhDecsn",
            amount_fields=("inhdtl_inhprc",),
            label="증설결정(유형자산 양수)",
        ),
    ),
    (
        "유형자산 양수",
        DartDetailRoute(
            endpoint="tgastInhDecsn",
            amount_fields=("inhdtl_inhprc",),
            label="유형자산 양수",
        ),
    ),
    (
        "유형자산 양도",
        DartDetailRoute(
            endpoint="tgastTrfDecsn",
            amount_fields=("trfdtl_trfprc", "trfdtl_trfamt"),
            label="유형자산 양도",
        ),
    ),
    # 2) 유상증자 — apiId=2020023
    #    https://opendart.fss.or.kr/api/piicDecsn.json
    #    자금조달 목적별 분할 금액 (시설자금/영업양수자금/운영자금)을 우선 추출.
    (
        "유상증자 결정",
        DartDetailRoute(
            endpoint="piicDecsn",
            amount_fields=(
                "fcamt",   # 시설자금(원)
                "ovmt",    # 영업양수자금(원)
                "pamt",    # 운영자금(원)
                "ocamt",   # 기타자금(원)
                "tot_amt",
            ),
            label="유상증자",
        ),
    ),
    (
        "제3자배정",
        DartDetailRoute(
            endpoint="piicDecsn",
            amount_fields=("fcamt", "ovmt", "pamt", "ocamt", "tot_amt"),
            label="제3자배정 유상증자",
        ),
    ),
    # 3) 전환사채(CB) — apiId=2020033
    #    https://opendart.fss.or.kr/api/cvbdIsDecsn.json
    (
        "전환사채",
        DartDetailRoute(
            endpoint="cvbdIsDecsn",
            amount_fields=("bd_fta", "bd_isamt", "fta"),
            label="전환사채 발행",
        ),
    ),
    # 4) 타법인 주식·출자증권 양수/양도 — apiId=2020046/2020047
    #    https://opendart.fss.or.kr/api/otcprStkInvscrInhDecsn.json  (otcpr! 표기 주의)
    #    https://opendart.fss.or.kr/api/otcprStkInvscrTrfDecsn.json
    (
        "타법인주식 및 출자증권 양수",
        DartDetailRoute(
            endpoint="otcprStkInvscrInhDecsn",
            amount_fields=("inhdtl_inhprc",),
            label="타법인 주식·출자증권 양수",
        ),
    ),
    (
        "타법인주식 및 출자증권 취득",
        DartDetailRoute(
            endpoint="otcprStkInvscrInhDecsn",
            amount_fields=("inhdtl_inhprc",),
            label="타법인 주식·출자증권 양수",
        ),
    ),
    (
        "출자증권 취득",
        DartDetailRoute(
            endpoint="otcprStkInvscrInhDecsn",
            amount_fields=("inhdtl_inhprc",),
            label="타법인 주식·출자증권 양수",
        ),
    ),
    (
        "타법인 주식",
        DartDetailRoute(
            endpoint="otcprStkInvscrInhDecsn",
            amount_fields=("inhdtl_inhprc",),
            label="타법인 주식 양수",
        ),
    ),
    (
        "타법인주식 및 출자증권 양도",
        DartDetailRoute(
            endpoint="otcprStkInvscrTrfDecsn",
            amount_fields=("trfdtl_trfprc",),
            label="타법인 주식·출자증권 양도",
        ),
    ),
    (
        "타법인주식 및 출자증권 처분",
        DartDetailRoute(
            endpoint="otcprStkInvscrTrfDecsn",
            amount_fields=("trfdtl_trfprc",),
            label="타법인 주식·출자증권 양도",
        ),
    ),
    (
        "출자증권 처분",
        DartDetailRoute(
            endpoint="otcprStkInvscrTrfDecsn",
            amount_fields=("trfdtl_trfprc",),
            label="타법인 주식·출자증권 양도",
        ),
    ),
    # 5) M&A 계열 — apiId 2020050~2020053, 2020042~2020043
    # cmpMgDecsn 응답에는 단일 합병 거래대가 필드가 없으며, 소멸회사 총자산(rbsnfdtl_tast)
    # 을 거래 규모의 대용 지표(proxy)로 사용한다.
    (
        "회사분할합병",
        DartDetailRoute(
            endpoint="cmpDvmgDecsn",
            amount_fields=("rbsnfdtl_tast", "rbsnfdtl_teqt", "tot_amt"),
            label="회사분할합병",
        ),
    ),
    (
        "회사합병",
        DartDetailRoute(
            endpoint="cmpMgDecsn",
            amount_fields=("rbsnfdtl_tast", "rbsnfdtl_teqt", "tot_amt"),
            label="회사합병(소멸회사 총자산 기준)",
        ),
    ),
    (
        "회사분할",
        DartDetailRoute(
            endpoint="cmpDvDecsn",
            amount_fields=("rbsnfdtl_tast", "rbsnfdtl_teqt", "tot_amt"),
            label="회사분할",
        ),
    ),
    (
        "주식교환",
        DartDetailRoute(
            endpoint="stkExtrDecsn",
            amount_fields=("tot_amt", "excg_amt", "rbsnfdtl_tast"),
            label="주식교환·이전",
        ),
    ),
    (
        "주식이전",
        DartDetailRoute(
            endpoint="stkExtrDecsn",
            amount_fields=("tot_amt", "excg_amt", "rbsnfdtl_tast"),
            label="주식교환·이전",
        ),
    ),
    (
        "영업양수",
        DartDetailRoute(
            endpoint="bsnInhDecsn",
            amount_fields=("inhdtl_inhprc", "inh_prm", "tot_inh_amt", "tot_amt"),
            label="영업양수",
        ),
    ),
    (
        "영업양도",
        DartDetailRoute(
            endpoint="bsnTrfDecsn",
            amount_fields=("trfdtl_trfprc", "trf_prm", "tot_trf_amt", "tot_amt"),
            label="영업양도",
        ),
    ),
    # 자산양수도(기타) — apiId=2020018, endpoint 명 미확정. 라우팅 보류.
)


_CORRECTION_PREFIX_RE = re.compile(r"^\s*\[\s*정정\s*[^\]]*\]\s*", re.UNICODE)


def route_for_title(title: str) -> Optional[DartDetailRoute]:
    """공시 제목 → 가장 구체적인 상세 API 라우팅.

    "[정정사항]" / "[기재정정]" 등 정정 공시 접두사는 원본 보고서와 동일한 endpoint 를 쓰므로
    매칭 전 제거한다.
    """
    if not title:
        return None
    cleaned = _CORRECTION_PREFIX_RE.sub("", title)
    for keyword, route in _TITLE_ROUTES:
        if keyword in cleaned:
            return route
    return None


_NON_DIGIT_RE = re.compile(r"[^\d-]")


def _to_int_amount(raw: Any) -> Optional[int]:
    """DART 응답 금액 문자열(콤마·단위 혼재)을 정수로 변환. 음수 부호 보존."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s == "-":
        return None
    cleaned = _NON_DIGIT_RE.sub("", s)
    if not cleaned or cleaned in ("-", "--"):
        return None
    try:
        v = int(cleaned)
    except ValueError:
        return None
    return v if v else None


def extract_amount(detail: dict, fields: tuple[str, ...]) -> Optional[int]:
    """우선순위 후보 필드 중 첫 번째 유효 정수 값을 반환."""
    for f in fields:
        v = _to_int_amount(detail.get(f))
        if v is not None and v > 0:
            return v
    # 후보 필드가 모두 비었거나 0인 경우, 응답 전체에서 '_amt' 또는 '_prm' 으로
    # 끝나는 가장 큰 양수 필드를 보조 추출 (best-effort, 잘못된 필드 보호).
    fallback_max = 0
    for k, v in detail.items():
        if not isinstance(k, str):
            continue
        if not (k.endswith("_amt") or k.endswith("_prm")):
            continue
        amt = _to_int_amount(v)
        if amt is not None and amt > fallback_max:
            fallback_max = amt
    return fallback_max or None


def extract_target_name(detail: dict) -> Optional[str]:
    """피인수·피투자 회사명 / 거래상대방 (DART 공식 응답 키 기준)."""
    for k in (
        "mgptncmp_cmpnm",  # 합병상대회사명 (cmpMgDecsn)
        "iscmp_cmpnm",     # 발행회사(회사명) — 타법인 양수 시 투자 대상
        "dlptn_cmpnm",     # 거래상대방(회사명/성명)
        "dvhv_cmpnm",      # 분할회사명
        "trfobj_cmpnm",    # 양도 대상 회사명
        "nmgcmp_cmpnm",    # 합병신설회사명
    ):
        v = detail.get(k)
        if v and str(v).strip() and str(v).strip() != "-":
            return str(v).strip()[:255]
    return None


async def fetch_detail(
    client: httpx.AsyncClient,
    api_key: str,
    endpoint: str,
    *,
    rcept_no: str,
    corp_code: str,
    rcept_dt: str,
) -> Optional[dict]:
    """단일 상세 API 호출 → 응답 list 항목 중 `rcept_no` 일치 dict 반환.

    DART 주요사항보고서 상세 API는 `corp_code` + `bgn_de` + `end_de` 가 필수이며,
    같은 회사·기간의 여러 공시가 한 응답에 포함될 수 있으므로 `rcept_no` 로 정확 매칭한다.
    """
    if not corp_code or not rcept_dt or len(rcept_dt) != 8:
        logger.debug(
            "DART %s 상세 조회 스킵 (corp_code/rcept_dt 누락) rcpt=%s",
            endpoint,
            rcept_no,
        )
        return None

    url = f"{_DART_BASE}/{endpoint}.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": rcept_dt,
        "end_de": rcept_dt,
    }
    try:
        resp = await client.get(url, params=params, timeout=30.0)
    except httpx.HTTPError as e:
        logger.warning("DART %s 상세 조회 네트워크 오류 rcpt=%s: %s", endpoint, rcept_no, e)
        return None

    if resp.status_code != 200:
        logger.warning(
            "DART %s 상세 조회 HTTP %s rcpt=%s body_prefix=%r",
            endpoint,
            resp.status_code,
            rcept_no,
            resp.text[:200] if resp.text else "",
        )
        return None

    try:
        body = resp.json()
    except ValueError:
        logger.warning("DART %s 상세 JSON 파싱 실패 rcpt=%s", endpoint, rcept_no)
        return None

    status = str(body.get("status") or "").strip()
    # status "013" = 조회된 데이터가 없습니다 (보고서 유형 미스매치 — 경미한 경고 수준)
    if status and status != "000":
        if status == "013":
            logger.debug(
                "DART %s no-data rcpt=%s msg=%s", endpoint, rcept_no, body.get("message")
            )
        else:
            logger.warning(
                "DART %s 비정상 status=%s rcpt=%s msg=%s",
                endpoint,
                status,
                rcept_no,
                body.get("message"),
            )
        return None

    items = body.get("list") or []
    if not isinstance(items, list) or not items:
        return None

    # 같은 회사·날짜의 여러 보고서가 들어올 수 있으므로 rcept_no 정확 매칭 우선.
    for it in items:
        if isinstance(it, dict) and str(it.get("rcept_no") or "").strip() == rcept_no:
            return it
    # 매칭 실패 시 첫 dict 사용 (단건 보고서일 가능성)
    for it in items:
        if isinstance(it, dict):
            return it
    return None
