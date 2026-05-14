"""중소벤처기업부 사업공고 OpenAPI 기반 Bronze 수집.

가이드: `backend/domain/master/docs/SMES_OPENAPI_COLLECTION_GUIDE.md`

공공 API 4대 함정 방어:
  1) xmltodict 의 List vs Dict 변환 함정 → `_ensure_list()`
  2) `published_at`: v2 응답에 등록일 필드가 없을 때 **옵션 B** —
     `applicationStartDate` 를 KST 자정으로 매핑하고
     `raw_metadata["published_at_source"] = "applicationStartDate"` 로 출처 기록.
     (레거시 필드 `regDt` 등이 있으면 그쪽을 우선.)
  3) `dataContents` / `pblancCn` HTML·CDATA 정제 금지 → 원형 그대로 `raw_content` 보존
  4) `source_url` 누락 / 잘못된 URL → 3단계 Fallback (정상 URL → 공고 ID 조합 → 기업마당 메인)

엔드포인트 (공공데이터포털 mssBizService_v2):
  - https://apis.data.go.kr/1421000/mssBizService_v2/getBizList_v2
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import aiohttp
import xmltodict

from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)

# 공공기관 공고는 한국시간 기준이므로 TIMESTAMPTZ 에 +09:00 고정 오프셋으로 저장.
_KST = timezone(timedelta(hours=9))

# 함정 4 — Fallback URL
_BIZINFO_BASE = "https://www.bizinfo.go.kr"
_BIZINFO_DETAIL = (
    "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId="
)

# 응답에서 정상으로 인정할 URL prefix (중기부 본부 게시판 등)
_VALID_URL_PREFIXES: tuple[str, ...] = (
    "https://www.bizinfo.go.kr",
    "http://www.bizinfo.go.kr",
    "https://www.mss.go.kr",
    "http://www.mss.go.kr",
    "https://www.smes.go.kr",
    "http://www.smes.go.kr",
)


def _ensure_list(value: Any) -> list:
    """함정 1 — xmltodict 결과를 항상 list 로 정규화.

    - 단일 element → dict 로 옴   → [dict] 로 감싼다.
    - element 없음 → None 또는 빈 문자열 → [] 반환.
    """
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _parse_date_to_kst(date_str: Optional[str]) -> Optional[datetime]:
    """`YYYYMMDD` 또는 `YYYY-MM-DD` 문자열을 해당 일자 00:00 KST 로 변환."""
    if not date_str:
        return None
    s = str(date_str).strip().replace("-", "").replace(".", "").replace("/", "")
    if len(s) < 8 or not s[:8].isdigit():
        return None
    try:
        return datetime.strptime(s[:8], "%Y%m%d").replace(tzinfo=_KST)
    except ValueError:
        return None


def _to_api_date_param(value: Optional[str]) -> Optional[str]:
    """쿼리용 날짜를 API 명세 `YYYY-MM-DD` 로 정규화.

    허용 입력: `YYYYMMDD`, `YYYY-MM-DD`, 빈 값.
    """
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    digits = s.replace("-", "").replace(".", "").replace("/", "")
    if len(digits) >= 8 and digits[:8].isdigit():
        y, m, d = digits[:4], digits[4:6], digits[6:8]
        return f"{y}-{m}-{d}"
    return None


def _classify_source_type(title: str) -> str:
    """공고명 키워드로 source_type 자동 분류."""
    if any(k in title for k in ("창업", "예비창업", "초기창업")):
        return "SMES_STARTUP"
    if any(k in title for k in ("연구개발", "R&D", "기술개발", "R&amp;D")):
        return "SMES_RND"
    if any(k in title for k in ("수출", "해외진출", "글로벌")):
        return "SMES_EXPORT"
    if any(k in title for k in ("스케일업", "성장", "도약")):
        return "SMES_SCALE_UP"
    return "SMES_GRANT"


class SmesOpenAPICollector:
    """중소벤처기업부 사업공고 OpenAPI Collector.

    - BASE_URL: 공공데이터포털 `mssBizService_v2` — `getbizList_v2`
    - 응답: XML (공공데이터포털 표준 wrapping: `response.header.resultCode` / `response.body.items.item`)
    """

    BASE_URL = (
        "https://apis.data.go.kr/1421000/mssBizService_v2/getbizList_v2"
    )

    # 응답에서 raw_title 로 매핑 가능한 후보 필드 (v2 `title` 우선)
    _TITLE_FIELDS: tuple[str, ...] = ("title", "pblancNm", "pbancNm")
    _HOST_FIELDS: tuple[str, ...] = ("insttNm", "jrsdInsttNm", "orgName")
    # v2 본문 필드 `dataContents` 우선
    _CONTENT_FIELDS: tuple[str, ...] = ("dataContents", "pblancCn", "pbancCn", "bizPblancCn")
    # 등록·게시일(레거시) 우선, 없으면 옵션 B 로 `applicationStartDate` 사용
    _PUBLISHED_FIELDS: tuple[str, ...] = ("regDt", "creatDt", "rgsDt", "bltnBgn")
    _PUBLISHED_OPTION_B_FIELDS: tuple[str, ...] = ("applicationStartDate",)
    _DEADLINE_FIELDS: tuple[str, ...] = (
        "applicationEndDate",
        "rcptEnd",
        "rcritEndDt",
        "reqstEndDt",
    )
    _URL_FIELDS: tuple[str, ...] = ("viewUrl", "pblancUrl", "pbancUrl", "url")
    _ID_FIELDS: tuple[str, ...] = ("itemId", "pblancId", "pbancId")

    def __init__(self, service_key: str):
        if not service_key or not service_key.strip():
            raise ValueError(
                "SMES API 키가 비어 있습니다. SMES_SERVICE_KEY 를 설정하세요."
            )
        # 공공데이터포털 키는 URL 인코딩하지 않은 원본을 그대로 사용 (aiohttp 가 1회 인코딩).
        self._service_key = service_key.strip()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def collect(
        self,
        *,
        max_items: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[OpportunityCollectDto]:
        """중소벤처 공고 수집 (페이지네이션 자동 처리)."""
        page_no = 1
        page_size = min(max_items, 100)
        collected: list[OpportunityCollectDto] = []
        seen_urls: set[str] = set()

        while len(collected) < max_items:
            remaining = max_items - len(collected)
            try:
                items = await self._fetch_page(
                    page_no=page_no,
                    num_of_rows=min(page_size, remaining if remaining > 0 else page_size),
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception:
                logger.exception("SMES API 페이지 %s 호출 실패", page_no)
                break

            if not items:
                break

            for item in items:
                try:
                    dto = self._parse_item(item)
                except Exception:
                    logger.warning(
                        "SMES 아이템 파싱 실패, 스킵: id=%s",
                        self._pick(item, self._ID_FIELDS),
                    )
                    continue
                if dto is None:
                    continue
                if dto.source_url in seen_urls:
                    continue
                seen_urls.add(dto.source_url)
                collected.append(dto)
                if len(collected) >= max_items:
                    break

            if len(items) < page_size:
                break  # 마지막 페이지
            page_no += 1

        logger.info(
            "SMES 수집 완료: %s건 (page=%s까지)", len(collected), page_no
        )
        return collected

    # ------------------------------------------------------------------
    # Internal — HTTP
    # ------------------------------------------------------------------

    async def _fetch_page(
        self,
        *,
        page_no: int,
        num_of_rows: int,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> list[dict]:
        params: dict[str, str] = {
            "serviceKey": self._service_key,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows),
        }
        if sd := _to_api_date_param(start_date):
            params["startDate"] = sd
        if ed := _to_api_date_param(end_date):
            params["endDate"] = ed

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(self.BASE_URL, params=params) as resp:
                    if resp.status != 200:
                        raise RuntimeError(
                            f"SMES API HTTP {resp.status} (page={page_no})"
                        )
                    body_text = await resp.text()
            except aiohttp.ClientError as e:
                raise RuntimeError(f"SMES API 네트워크 오류: {e}") from e

        return self._extract_items(body_text)

    def _extract_items(self, body_text: str) -> list[dict]:
        """XML/JSON 양쪽을 모두 받아 item 리스트로 정규화."""
        text = (body_text or "").strip()
        if not text:
            return []

        # XML 우선 (공공데이터포털 기본)
        try:
            data = xmltodict.parse(text)
        except Exception:
            # JSON 응답일 수 있음
            try:
                import json

                data = json.loads(text)
            except Exception:
                logger.error(
                    "SMES 응답을 XML/JSON 어느 쪽으로도 파싱하지 못함: %s",
                    text[:200],
                )
                return []

        # 공공데이터포털 표준 구조 검증.
        # 1순위: data["response"] (공공데이터포털 표준 wrapping)
        # 2순위: data 자체 (간소화된 JSON 응답)
        if not isinstance(data, dict):
            return []
        response = data.get("response")
        if not isinstance(response, dict):
            response = data

        header = response.get("header") if isinstance(response.get("header"), dict) else {}
        result_code = str(header.get("resultCode") or header.get("RESULT_CODE") or "").strip()
        if result_code and result_code not in (
            "00",
            "0",
            "0000",
            "INFO-0",
            "INFO_0",
            "NORMAL_CODE",
        ):
            logger.warning(
                "SMES API 비정상 응답: code=%s msg=%s",
                result_code,
                header.get("resultMsg") or header.get("RESULT_MSG"),
            )
            return []

        body = response.get("body") if isinstance(response.get("body"), dict) else response

        # 함정 1 — items 위치 후보군 모두 시도
        items_wrapper = body.get("items") if isinstance(body, dict) else None

        if isinstance(items_wrapper, dict):
            items = _ensure_list(items_wrapper.get("item"))
        elif isinstance(items_wrapper, list):
            items = items_wrapper
        else:
            # 일부 API 는 body 바로 아래에 item 이 옴
            items = _ensure_list(body.get("item") if isinstance(body, dict) else None)

        # 타입 정규화 (모든 원소가 dict 인지)
        return [it for it in items if isinstance(it, dict)]

    # ------------------------------------------------------------------
    # Internal — Mapping (4대 함정 방어)
    # ------------------------------------------------------------------

    @staticmethod
    def _pick(item: dict, fields: tuple[str, ...]) -> Optional[str]:
        """후보 필드 중 가장 먼저 값이 채워진 것을 반환."""
        for f in fields:
            value = item.get(f)
            if value is None:
                continue
            s = str(value).strip()
            if s:
                return s
        return None

    def _resolve_source_url(self, item: dict) -> str:
        """함정 4 — source_url 3단계 Fallback (NOT NULL 보장)."""
        url = self._pick(item, self._URL_FIELDS) or ""
        if url.startswith(_VALID_URL_PREFIXES):
            return url

        pblanc_id = self._pick(item, self._ID_FIELDS)
        if pblanc_id:
            return f"{_BIZINFO_DETAIL}{pblanc_id}"

        return _BIZINFO_BASE

    def _resolve_published_at(
        self, item: dict
    ) -> tuple[Optional[datetime], Optional[str]]:
        """게시·등록 시각 + 출처 필드명.

        레거시(`regDt` 등)가 있으면 우선.
        v2 는 등록일 필드가 없어 **옵션 B**: `applicationStartDate` 를 `published_at` 으로 사용
        (Silver/운영에서 `published_at_source` 로 구분).
        """
        for field in self._PUBLISHED_FIELDS:
            parsed = _parse_date_to_kst(item.get(field))
            if parsed:
                return parsed, field
        for field in self._PUBLISHED_OPTION_B_FIELDS:
            parsed = _parse_date_to_kst(item.get(field))
            if parsed:
                return parsed, field
        return None, None

    def _resolve_deadline_at(self, item: dict) -> Optional[datetime]:
        for field in self._DEADLINE_FIELDS:
            parsed = _parse_date_to_kst(item.get(field))
            if parsed:
                return parsed
        return None

    @staticmethod
    def _build_attachments(item: dict) -> list[dict[str, str]]:
        """함정 1 — `fileName`/`fileUrl` 반복 태그를 attachments 배열로 정규화."""
        names = _ensure_list(item.get("fileName"))
        urls = _ensure_list(item.get("fileUrl"))
        out: list[dict[str, str]] = []
        for n, u in zip(names, urls):
            name = str(n).strip() if n is not None else ""
            url = str(u).strip() if u is not None else ""
            if name and url:
                out.append({"name": name, "url": url})
        return out

    @staticmethod
    def _build_contact(item: dict) -> dict[str, str] | None:
        """v2 담당자·부서 정보."""
        name = (item.get("writerName") or "").strip()
        position = (item.get("writerPosition") or "").strip()
        phone = (item.get("writerPhone") or "").strip()
        email = (item.get("writerEmail") or "").strip()
        if not (name or position or phone or email):
            return None
        return {
            "name": name,
            "position": position,
            "phone": phone,
            "email": email,
        }

    def _resolve_host_name(self, item: dict) -> str | None:
        """주관기관: API 필드가 있으면 사용, 없으면 중기부 + 소관과(옵션 B)."""
        direct = self._pick(item, self._HOST_FIELDS)
        if direct:
            return direct[:150]
        dept = (item.get("writerPosition") or "").strip()
        if dept:
            return f"중소벤처기업부 {dept}"[:150]
        return "중소벤처기업부"[:150]

    def _parse_item(self, item: dict) -> Optional[OpportunityCollectDto]:
        """XML item → OpportunityCollectDto."""
        raw_title = self._pick(item, self._TITLE_FIELDS)
        if not raw_title:
            return None

        host_name = self._resolve_host_name(item)

        # 함정 3 — 본문 HTML / CDATA 원형 그대로 보존
        raw_content = self._pick(item, self._CONTENT_FIELDS)

        published_at, published_src = self._resolve_published_at(item)
        deadline_at = self._resolve_deadline_at(item)

        # 함정 4 — source_url 3단계 Fallback (NOT NULL 보장)
        source_url = self._resolve_source_url(item)

        source_type = _classify_source_type(raw_title)

        app_start = (
            item.get("applicationStartDate")
            or item.get("rcritStrtDt")
            or item.get("rcptBgn")
            or item.get("reqstBgnDt")
        )
        app_end = (
            item.get("applicationEndDate")
            or item.get("rcptEnd")
            or item.get("rcritEndDt")
            or item.get("reqstEndDt")
        )

        raw_metadata: dict[str, Any] = {
            "announcement_id": self._pick(item, self._ID_FIELDS),
            "bulletin_period": {
                "start": item.get("bltnBgn") or item.get("pbancBgnDt"),
                "end": item.get("bltnEnd") or item.get("pbancEndDt"),
            },
            "application_period": {"start": app_start, "end": app_end},
            "budget": item.get("scaleAmt") or item.get("totSportPrcPo"),
            "attachment_file_id": item.get("atchFileId") or item.get("atchmnflId"),
            "original_pblanc_url": self._pick(item, self._URL_FIELDS),
        }
        if published_src:
            raw_metadata["published_at_source"] = published_src
        if contact := self._build_contact(item):
            raw_metadata["contact"] = contact
        if attachments := self._build_attachments(item):
            raw_metadata["attachments"] = attachments
        raw_metadata["original_item"] = item

        return OpportunityCollectDto(
            source_type=source_type,
            source_url=source_url,
            raw_title=raw_title[:500],
            host_name=host_name,
            raw_content=raw_content,
            raw_metadata=raw_metadata,
            published_at=published_at,
            deadline_at=deadline_at,
        )

    # ------------------------------------------------------------------
    # Sync helper (스레드 오프로딩 없이 직접 호출하려는 스크립트용)
    # ------------------------------------------------------------------

    def collect_sync(
        self,
        *,
        max_items: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[OpportunityCollectDto]:
        return asyncio.run(
            self.collect(
                max_items=max_items, start_date=start_date, end_date=end_date
            )
        )
