"""재정경제부 공공기관 사업정보 OpenAPI 기반 Bronze 수집 (`raw_economic_data`).

공공데이터포털 API ID: `15125286` (서비스명: 재정경제부_공공기관 사업정보 조회서비스).
실제 호출 URL은 포털 개발계정·명세의 **Base `.../1051000/biz` + `/list`** 이다.
코드값(`bizClsf`, `lifecyclLst`, `instCd` 등)은 `MOEF_NKOD_DB_05_코드 정의서` PDF와 대조한다.

가이드: `backend/domain/master/docs/ALIO_COLLECTION_STRATEGY.md`
xmltodict 단일/복수 element, 필드명 변형, source_url NOT NULL 보장 등은
`smes_collector.py` 와 동일한 패턴으로 처리한다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import quote

import aiohttp
import xmltodict

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))

_ALIO_HOST_PREFIXES: tuple[str, ...] = (
    "https://www.alio.go.kr",
    "http://www.alio.go.kr",
    "https://job.alio.go.kr",
    "http://job.alio.go.kr",
)

_ALIO_FALLBACK_BASE = "https://www.alio.go.kr/"

_KEYWORDS: tuple[str, ...] = (
    "AI",
    "인공지능",
    "데이터",
    "소프트웨어",
    "클라우드",
    "디지털",
    "스마트",
    "IoT",
    "블록체인",
    "사이버보안",
    "R&D",
    "연구개발",
    "기술개발",
    "혁신",
    "첨단",
    "스타트업",
    "창업",
    "벤처",
    "중소기업",
    "소상공인",
    "지원사업",
    "지원금",
    "보조금",
    "바우처",
    "공모",
    "ESG",
    "탄소중립",
    "친환경",
    "신재생",
)

DEFAULT_INST_WHITELIST: tuple[str, ...] = (
    "한국산업기술진흥원",
    "중소벤처기업진흥공단",
    "창업진흥원",
    "한국연구재단",
    "정보통신산업진흥원",
    "한국인터넷진흥원",
    "한국전자통신연구원",
    "한국과학기술정보연구원",
    "한국에너지기술평가원",
)


def _ensure_list(value: Any) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _parse_datetime_kst(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    if len(digits) >= 14 and digits[:14].isdigit():
        try:
            dt = datetime.strptime(digits[:14], "%Y%m%d%H%M%S")
            return dt.replace(tzinfo=_KST)
        except ValueError:
            pass
    if len(digits) >= 8 and digits[:8].isdigit():
        try:
            return datetime.strptime(digits[:8], "%Y%m%d").replace(tzinfo=_KST)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[: len(fmt)], fmt)
            return dt.replace(tzinfo=_KST)
        except ValueError:
            continue
    return None


def _classify_source_type(title: str) -> str:
    t = title or ""
    if any(k in t for k in ("R&D", "연구개발", "기술개발")):
        return "GOVT_ALIO_RND"
    if any(k in t for k in ("창업", "스타트업", "예비창업")):
        return "GOVT_ALIO_STARTUP"
    if any(k in t for k in ("중소기업", "소상공인")):
        return "GOVT_ALIO_SME"
    return "GOVT_ALIO_PROJECT"


def _matches_keyword(biz_nm: str, biz_purpose: str | None) -> bool:
    combined = f"{biz_nm or ''} {biz_purpose or ''}"
    cf = combined.casefold()
    for kw in _KEYWORDS:
        needle = kw.casefold() if kw.isascii() else kw
        hay = cf if kw.isascii() else combined
        if needle in hay:
            return True
    return False


def _inst_passes_whitelist(inst_nm: str | None, whitelist: tuple[str, ...] | None) -> bool:
    if whitelist is None:
        return True
    if not inst_nm:
        return False
    for w in whitelist:
        if w and w in inst_nm:
            return True
    return False


class AlioPublicInstProjectCollector:
    """재정경제부 NKOD 사업정보 목록 OpenAPI Collector (`GET .../biz/list`)."""

    BASE_URL = "https://apis.data.go.kr/1051000/biz/list"

    # 2026-05-14 실측: API ID 15125286 응답 21개 필드 기준으로 정정.
    # 응답에 budget/bizBudget 등 예산 필드는 존재하지 않음 (사업 카탈로그만 제공).
    # 예산은 NTIS·KONEPS 등 별도 소스에서 보완해야 함.
    _TITLE_FIELDS: tuple[str, ...] = ("bizNm",)
    _INST_FIELDS: tuple[str, ...] = ("instNm",)
    _PURPOSE_FIELDS: tuple[str, ...] = ("bizExpln",)
    # `bgngYmd` 사업 개시일(YYYYMMDD) 우선, 비어 있으면 `endYmd`(종료일) 차순.
    # 두 필드 모두 null 인 사업이 다수(상시·운영형) — published_at None 허용.
    _PUBLISHED_FIELDS: tuple[str, ...] = ("bgngYmd", "endYmd")
    _BIZ_ID_FIELDS: tuple[str, ...] = ("bizSn",)
    _DETAIL_URL_FIELDS: tuple[str, ...] = ("siteUrl",)
    _TARGET_FIELDS: tuple[str, ...] = ("utztnTrgtExpln",)
    _PERIOD_FIELDS: tuple[str, ...] = ("bizPeriodExpln",)
    _CATEGORY_FIELDS: tuple[str, ...] = ("bizClsfNm", "bizClsf", "srvcClsfNm", "srvcClsf")
    _METHOD_FIELDS: tuple[str, ...] = ("utztnMthdExpln",)
    _CONTACT_FIELDS: tuple[str, ...] = ("utztnInqInfo",)
    _LIFECYCLE_NAME_FIELDS: tuple[str, ...] = ("lifecyclNmLst",)
    _LIFECYCLE_CODE_FIELDS: tuple[str, ...] = ("lifecyclLst",)
    _PERIOD_SE_FIELDS: tuple[str, ...] = ("bizPeriodSeNm", "bizPeriodSe")
    _INST_CODE_FIELDS: tuple[str, ...] = ("instCd",)
    _STD_INST_CODE_FIELDS: tuple[str, ...] = ("pbadmsStdInstCd",)
    _BGNG_YMD_FIELDS: tuple[str, ...] = ("bgngYmd",)
    _END_YMD_FIELDS: tuple[str, ...] = ("endYmd",)

    def __init__(self, service_key: str):
        if not service_key or not service_key.strip():
            raise ValueError(
                "ALIO API 키가 비어 있습니다. ALIO_SERVICE_KEY 를 설정하세요."
            )
        self._service_key = service_key.strip()

    async def collect(
        self,
        *,
        max_items: int = 200,
        inst_filter: list[str] | None = None,
        biz_year: int | None = None,
        disable_keyword_filter: bool = False,
    ) -> list[EconomicCollectDto]:
        if inst_filter is None:
            inst_whitelist: tuple[str, ...] | None = DEFAULT_INST_WHITELIST
        elif len(inst_filter) == 0:
            inst_whitelist = None
        else:
            inst_whitelist = tuple(inst_filter)

        page_no = 1
        page_size = min(max_items, 100)
        collected: list[EconomicCollectDto] = []
        seen_urls: set[str] = set()

        while len(collected) < max_items:
            remaining = max_items - len(collected)
            num_rows = min(page_size, remaining if remaining > 0 else page_size)
            try:
                items = await self._fetch_page(
                    page_no=page_no,
                    num_of_rows=num_rows,
                )
            except Exception:
                logger.exception("ALIO API 페이지 %s 호출 실패", page_no)
                break

            if not items:
                break

            for item in items:
                try:
                    dto = self._parse_item(
                        item,
                        inst_whitelist=inst_whitelist,
                        disable_keyword_filter=disable_keyword_filter,
                        biz_year_filter=biz_year,
                    )
                except Exception:
                    logger.warning(
                        "ALIO 아이템 파싱 실패, 스킵: biz_id=%s",
                        self._pick(item, self._BIZ_ID_FIELDS),
                    )
                    continue
                if dto is None:
                    continue
                url_key = dto.source_url or ""
                if url_key in seen_urls:
                    continue
                seen_urls.add(url_key)
                collected.append(dto)
                if len(collected) >= max_items:
                    break

            if len(items) < num_rows:
                break
            page_no += 1

        logger.info("ALIO 수집 완료: %s건 (page=%s까지)", len(collected), page_no)
        return collected

    async def _fetch_page(
        self,
        *,
        page_no: int,
        num_of_rows: int,
    ) -> list[dict]:
        params: dict[str, str] = {
            "serviceKey": self._service_key,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows),
            "resultType": "json",
        }

        timeout = aiohttp.ClientTimeout(total=45)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(self.BASE_URL, params=params) as resp:
                    body_text = await resp.text()
                    if resp.status != 200:
                        logger.error(
                            "ALIO API HTTP %s (page=%s) body_prefix=%r",
                            resp.status,
                            page_no,
                            (body_text or "")[:800],
                        )
                        raise RuntimeError(
                            f"ALIO API HTTP {resp.status} (page={page_no})"
                        )
            except aiohttp.ClientError as e:
                raise RuntimeError(f"ALIO API 네트워크 오류: {e}") from e

        return self._extract_items(body_text)

    def _extract_items(self, body_text: str) -> list[dict]:
        text = (body_text or "").strip()
        if not text:
            return []

        if text.startswith("{"):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
            else:
                if isinstance(data, dict):
                    nkod = self._extract_moef_nkod_json_items(data)
                    if nkod is not None:
                        return nkod
                    legacy = self._extract_legacy_response_items(data)
                    if legacy is not None:
                        return legacy

        try:
            data = xmltodict.parse(text)
        except Exception:
            if not text.startswith("{"):
                try:
                    data = json.loads(text)
                except Exception:
                    logger.error(
                        "ALIO 응답을 XML/JSON 으로 파싱하지 못함: %s",
                        text[:200],
                    )
                    return []
                if isinstance(data, dict):
                    nkod = self._extract_moef_nkod_json_items(data)
                    if nkod is not None:
                        return nkod
                    legacy = self._extract_legacy_response_items(data)
                    return legacy if legacy is not None else []
            return []

        if isinstance(data, dict):
            legacy = self._extract_legacy_response_items(data)
            return legacy if legacy is not None else []
        return []

    def _extract_moef_nkod_json_items(self, data: dict) -> list[dict] | None:
        """`1051000/biz/list` NKOD JSON: `result` 배열·오류코드(resultCode)."""
        if "result" not in data:
            return None

        rc = data.get("resultCode")
        if rc is not None:
            s = str(rc).strip()
            if s in ("1", "2", "5", "6", "7", "10", "11"):
                logger.warning(
                    "ALIO(MOEF NKOD) 오류: resultCode=%s resultMsg=%s",
                    s,
                    data.get("resultMsg") or data.get("message"),
                )
                return []
            if s == "3":
                return []

        r = data.get("result")
        if isinstance(r, list):
            return [x for x in r if isinstance(x, dict)]
        if isinstance(r, dict):
            for key in ("list", "items", "data", "row", "resultList"):
                v = r.get(key)
                if isinstance(v, list):
                    return [x for x in v if isinstance(x, dict)]
                if isinstance(v, dict):
                    inner = _ensure_list(v.get("item"))
                    return [x for x in inner if isinstance(x, dict)]
            return []
        return []

    def _extract_legacy_response_items(self, data: dict) -> list[dict] | None:
        """공공데이터포털 표준 `response.header` / `response.body.items.item` 경로."""
        response = data.get("response")
        if not isinstance(response, dict):
            return None

        header = (
            response.get("header") if isinstance(response.get("header"), dict) else {}
        )
        result_code = str(
            header.get("resultCode") or header.get("RESULT_CODE") or ""
        ).strip()
        if result_code and result_code not in (
            "00",
            "0",
            "0000",
            "INFO-0",
            "INFO_0",
            "NORMAL_CODE",
        ):
            logger.warning(
                "ALIO API 비정상 응답: code=%s msg=%s",
                result_code,
                header.get("resultMsg") or header.get("RESULT_MSG"),
            )
            return []

        body = (
            response.get("body") if isinstance(response.get("body"), dict) else response
        )
        items_wrapper = body.get("items") if isinstance(body, dict) else None

        if isinstance(items_wrapper, dict):
            items = _ensure_list(items_wrapper.get("item"))
        elif isinstance(items_wrapper, list):
            items = items_wrapper
        else:
            items = _ensure_list(body.get("item") if isinstance(body, dict) else None)

        return [it for it in items if isinstance(it, dict)]

    @staticmethod
    def _pick(item: dict, fields: tuple[str, ...]) -> Optional[str]:
        for f in fields:
            value = item.get(f)
            if value is None:
                continue
            s = str(value).strip()
            if s:
                return s
        return None

    def _resolve_source_url(self, item: dict) -> str:
        site = (item.get("siteUrl") or "").strip()
        if site.startswith("http://") or site.startswith("https://"):
            return site

        detail = self._pick(item, self._DETAIL_URL_FIELDS) or ""
        if detail.startswith(_ALIO_HOST_PREFIXES):
            return detail

        biz_id = self._pick(item, self._BIZ_ID_FIELDS)
        if biz_id:
            return (
                "https://job.alio.go.kr/businessdetail.do"
                f"?bizId={quote(str(biz_id), safe='')}"
            )

        return _ALIO_FALLBACK_BASE

    def _parse_item(
        self,
        item: dict,
        *,
        inst_whitelist: tuple[str, ...] | None,
        disable_keyword_filter: bool,
        biz_year_filter: int | None,
    ) -> Optional[EconomicCollectDto]:
        raw_title = self._pick(item, self._TITLE_FIELDS)
        if not raw_title:
            return None

        inst_nm = self._pick(item, self._INST_FIELDS)
        if not _inst_passes_whitelist(inst_nm, inst_whitelist):
            return None

        biz_purpose = self._pick(item, self._PURPOSE_FIELDS)
        if not disable_keyword_filter and not _matches_keyword(raw_title, biz_purpose):
            return None

        bgng_ymd = self._pick(item, self._BGNG_YMD_FIELDS)
        end_ymd = self._pick(item, self._END_YMD_FIELDS)

        if biz_year_filter is not None:
            year_candidates = (bgng_ymd or "", end_ymd or "")
            yr_match = None
            for y_raw in year_candidates:
                y_digits = re.sub(r"\D", "", y_raw)[:4]
                if y_digits.isdigit():
                    yr_match = int(y_digits)
                    break
            if yr_match is not None and yr_match != biz_year_filter:
                return None

        published_at: datetime | None = None
        for f in self._PUBLISHED_FIELDS:
            published_at = _parse_datetime_kst(item.get(f))
            if published_at:
                break

        end_at = _parse_datetime_kst(end_ymd) if end_ymd else None

        source_url = self._resolve_source_url(item)
        source_type = _classify_source_type(raw_title)

        biz_id = self._pick(item, self._BIZ_ID_FIELDS)

        raw_metadata: dict[str, Any] = {
            "biz_sn": biz_id,
            "biz_expln": self._pick(item, ("bizExpln",)),
            "biz_target": self._pick(item, self._TARGET_FIELDS),
            "biz_period": self._pick(item, self._PERIOD_FIELDS),
            "biz_period_se": self._pick(item, self._PERIOD_SE_FIELDS),
            "biz_clsf": self._pick(item, ("bizClsf",)),
            "biz_clsf_nm": self._pick(item, ("bizClsfNm",)),
            "srvc_clsf": self._pick(item, ("srvcClsf",)),
            "srvc_clsf_nm": self._pick(item, ("srvcClsfNm",)),
            "inst_cd": self._pick(item, self._INST_CODE_FIELDS),
            "pbadms_std_inst_cd": self._pick(item, self._STD_INST_CODE_FIELDS),
            "lifecycl_lst": self._pick(item, self._LIFECYCLE_CODE_FIELDS),
            "lifecycl_nm_lst": self._pick(item, self._LIFECYCLE_NAME_FIELDS),
            "utztn_mthd_expln": self._pick(item, self._METHOD_FIELDS),
            "utztn_inq_info": self._pick(item, self._CONTACT_FIELDS),
            "site_url": self._pick(item, self._DETAIL_URL_FIELDS),
            "bgng_ymd": bgng_ymd,
            "end_ymd": end_ymd,
            # 실측: ALIO API ID 15125286 응답에는 예산(budget) 필드가 존재하지 않음 (사업 카탈로그만).
            # 예산 정량 데이터는 NTIS·KONEPS 등 별도 소스로 보완.
            "budget_available": False,
            "original_item": item,
        }
        if end_at is not None:
            raw_metadata["end_at"] = end_at.isoformat()

        return EconomicCollectDto(
            source_type=source_type,
            source_url=source_url,
            raw_title=raw_title[:500],
            investor_name=(inst_nm[:255] if inst_nm else None),
            target_company_or_fund=None,
            # ALIO API 응답에 예산 필드가 없어 영구적으로 None 유지.
            investment_amount=None,
            currency="KRW",
            published_at=published_at,
            raw_metadata=raw_metadata,
        )

    def collect_sync(
        self,
        *,
        max_items: int = 200,
        inst_filter: list[str] | None = None,
        biz_year: int | None = None,
        disable_keyword_filter: bool = False,
    ) -> list[EconomicCollectDto]:
        return asyncio.run(
            self.collect(
                max_items=max_items,
                inst_filter=inst_filter,
                biz_year=biz_year,
                disable_keyword_filter=disable_keyword_filter,
            )
        )
