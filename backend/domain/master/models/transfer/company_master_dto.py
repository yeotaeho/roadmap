"""검증 기업 마스터(verified_company_master) 수집 결과 DTO."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class CompanyMasterDto(BaseModel):
    source_type: str = Field(
        ..., max_length=50, description="VENTURE_CERTIFIED / KSTARTUP_PREUNICORN 등"
    )

    # 핵심 식별 정보
    company_name: str = Field(..., max_length=255, description="기업명 (필수)")
    business_number: Optional[str] = Field(
        default=None, max_length=20, description="사업자등록번호(10자리)"
    )
    corp_number: Optional[str] = Field(
        default=None, max_length=20, description="법인등록번호(13자리)"
    )
    ceo_name: Optional[str] = Field(default=None, max_length=100, description="대표자명")

    # 인증/선정 정보
    certification_type: Optional[str] = Field(default=None, max_length=100)
    certification_date: Optional[date] = None
    expiry_date: Optional[date] = None
    certifying_agency: Optional[str] = Field(default=None, max_length=150)

    # 기업 세부 정보
    industry_sector: Optional[str] = Field(default=None, max_length=100)
    establishment_date: Optional[date] = None
    address: Optional[str] = None

    # 확장·출처 정보
    raw_metadata: Optional[dict[str, Any]] = None
    source_file_url: Optional[str] = None
    source_file_version: Optional[str] = Field(default=None, max_length=50)

    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"str_strip_whitespace": True}
