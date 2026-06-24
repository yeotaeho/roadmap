# DART 기업개황으로 검증 기업 마스터를 보강한다 — 골격(corp_code 매핑 차기 구현)

from __future__ import annotations

import logging

from domain.master.models.transfer.company_master_dto import CompanyMasterDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "DART_COMPANY_OVERVIEW"

# DART 기업개황 API(opendart.fss.or.kr/api/company.json)는 corp_code 단건 조회이므로
# corpCode.xml(전체 고유번호 파일) 매핑이 선행돼야 한다. 차기 태스크에서 구현.
_API_URL = "https://opendart.fss.or.kr/api/company.json"


class DartOverviewCollector:
    """DART 기업개황 보강 — 현재는 골격(미구현). 항상 빈 결과 안전 반환."""

    def __init__(self, dart_api_key: str):
        if not dart_api_key or not dart_api_key.strip():
            raise ValueError("DART_API_KEY 가 설정되어 있지 않습니다.")
        self._key = dart_api_key.strip()

    async def collect(self, *, corp_codes: list[str] | None = None) -> tuple[list[CompanyMasterDto], dict[str, int]]:
        logger.info("[dart-overview] 골격 수집기 — corp_code 매핑 미구현. 빈 결과 반환.")
        return [], {"requested": len(corp_codes or []), "fetched": 0, "not_implemented": 1}


__all__ = ["DartOverviewCollector"]
