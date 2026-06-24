# 중소벤처기업부 벤처기업명단(data.go.kr fileData)에서 검증 기업 마스터를 수집한다

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any, Optional

import aiohttp

from domain.master.models.transfer.company_master_dto import CompanyMasterDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "VENTURE_CERTIFIED"
_AGENCY = "중소벤처기업부"

# data.go.kr 벤처기업명단(15084581) fileData → odcloud.kr OpenAPI 자동변환.
#   uddi 리소스 경로는 배포 버전마다 바뀌므로 키 발급 후 data.go.kr 상세에서 확인해 갱신.
#   기본 템플릿: https://api.odcloud.kr/api/15084581/v1/uddi:<resource>
# 2026-06-01판 리소스(39,668행). 배포(월) 갱신 시 data.go.kr 상세에서 확인해 교체하거나
# 라우터 ?resource= / VENTURE_LIST_RESOURCE 로 override.
_DEFAULT_RESOURCE = "uddi:47b202c9-f0bb-43b4-949c-ebe9ef56ef02"
_BASE_URL = "https://api.odcloud.kr/api/15084581/v1/"

# 실제 컬럼명(2026-06-01판 odcloud, 39,668행) 우선 + 변형 폴백.
_FIELD_NAME = ("업체명", "기업명", "회사명", "companyName", "company_name", "벤처기업명")
_FIELD_CEO = ("대표자명(익명)", "대표자명", "대표자", "ceoName", "대표")
_FIELD_CERT_TYPE = ("벤처확인유형", "벤처기업확인유형", "확인유형", "벤처유형")
_FIELD_REGION = ("지역", "소재지", "시도", "지역명")
_FIELD_ADDRESS = ("주소", "간략주소", "소재지주소", "address")
_FIELD_SECTOR = ("업종명(11차)", "업종분류(기보)", "업종", "업종분류", "업태", "주업종")
_FIELD_BIZNO = ("사업자등록번호", "사업자번호", "bizrno", "사업자")
_FIELD_CERT_DATE = ("벤처유효시작일", "확인일자", "벤처확인일", "유효기간시작일", "확인시작일")
_FIELD_EXPIRY = ("벤처유효종료일", "유효기간종료일", "확인종료일")
_FIELD_AGENCY = ("벤처확인기관", "확인기관")


def _pick(item: dict, fields: tuple[str, ...]) -> Optional[str]:
    for f in fields:
        value = item.get(f)
        if value is None:
            continue
        s = str(value).strip()
        if s:
            return s
    return None


def _normalize_bizno(value: Optional[str]) -> Optional[str]:
    """사업자등록번호를 숫자 10자리로 정규화. 형식 불일치 시 None."""
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 10 else None


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    s = re.sub(r"[^\d]", "", str(value))
    if len(s) < 8 or not s[:8].isdigit():
        return None
    try:
        return datetime.strptime(s[:8], "%Y%m%d").date()
    except ValueError:
        return None


def map_item(item: dict, *, file_version: str | None = None) -> Optional[CompanyMasterDto]:
    name = _pick(item, _FIELD_NAME)
    if not name:
        return None
    region = _pick(item, _FIELD_REGION)
    raw_metadata: dict[str, Any] = {"original_item": item}
    if region:
        raw_metadata["region"] = region
    for label, key in (("main_product", "주생산품"), ("renewal", "신규_재확인")):
        if val := _pick(item, (key,)):
            raw_metadata[label] = val
    return CompanyMasterDto(
        source_type=_SOURCE_TYPE,
        company_name=name[:255],
        business_number=_normalize_bizno(_pick(item, _FIELD_BIZNO)),
        ceo_name=(_pick(item, _FIELD_CEO) or None),
        certification_type=(_pick(item, _FIELD_CERT_TYPE) or None),
        certification_date=_parse_date(_pick(item, _FIELD_CERT_DATE)),
        expiry_date=_parse_date(_pick(item, _FIELD_EXPIRY)),
        certifying_agency=(_pick(item, _FIELD_AGENCY) or _AGENCY),
        industry_sector=(_pick(item, _FIELD_SECTOR) or None),
        address=(_pick(item, _FIELD_ADDRESS) or None),
        raw_metadata=raw_metadata,
        source_file_url="https://www.data.go.kr/data/15084581/fileData.do",
        source_file_version=file_version,
    )


def parse_payload(body_text: str, *, file_version: str | None = None) -> list[CompanyMasterDto]:
    """odcloud 응답(JSON data[])을 CompanyMasterDto 리스트로 변환."""
    text = (body_text or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except Exception:
        logger.error("벤처기업명단 응답 파싱 실패: %s", text[:200])
        return []
    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    out: list[CompanyMasterDto] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        dto = map_item(item, file_version=file_version)
        if dto:
            out.append(dto)
    return out


class VentureListCollector:
    """벤처기업명단 — 페이지 순회로 검증 기업 마스터 수집."""

    def __init__(self, service_key: str, *, resource: str | None = None):
        if not service_key or not service_key.strip():
            raise ValueError("벤처기업명단 API 키가 비어 있습니다. VENTURE_LIST_SERVICE_KEY 를 설정하세요.")
        self._service_key = service_key.strip()
        self._resource = (resource or _DEFAULT_RESOURCE).strip()

    async def collect(
        self, *, max_items: int = 1000, file_version: str | None = None
    ) -> tuple[list[CompanyMasterDto], dict[str, int]]:
        stats = {"requests_total": 0, "requests_ok": 0, "errors": 0, "fetched": 0}
        if not self._resource:
            logger.warning("[venture-list] uddi 리소스 경로 미설정 — 수집 스킵")
            return [], stats
        url = f"{_BASE_URL}{self._resource}"
        per_page = min(max_items, 1000)
        collected: list[CompanyMasterDto] = []
        page = 1
        timeout = aiohttp.ClientTimeout(total=40)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while len(collected) < max_items:
                stats["requests_total"] += 1
                params = {
                    "serviceKey": self._service_key,
                    "page": str(page),
                    "perPage": str(per_page),
                    "returnType": "JSON",
                }
                try:
                    async with session.get(url, params=params) as resp:
                        resp.raise_for_status()
                        body_text = await resp.text()
                    rows = parse_payload(body_text, file_version=file_version)
                    stats["requests_ok"] += 1
                except Exception:
                    stats["errors"] += 1
                    logger.exception("[venture-list] 수집 실패 page=%s", page)
                    break
                if not rows:
                    break
                collected.extend(rows)
                if len(rows) < per_page:
                    break
                page += 1
        stats["fetched"] = len(collected)
        return collected[:max_items], stats


__all__ = ["VentureListCollector", "parse_payload", "map_item"]
