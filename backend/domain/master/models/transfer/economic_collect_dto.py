"""경제 Bronze 수집 결과 DTO (Collector → Service → Repository)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class EconomicCollectDto(BaseModel):
    source_type: str = Field(
        ...,
        max_length=50,
        description="예: DART_M_AND_A, DART_FACILITY_INVEST, DART_CAPITAL_INCREASE, DART_OWNERSHIP_BULK",
    )
    source_url: Optional[str] = Field(default=None, description="원문/출처 URL")

    # 핵심 엔티티 정보
    raw_title: str = Field(..., max_length=500, description="공시 제목, 뉴스 헤드라인 (필수)")
    investor_name: Optional[str] = Field(default=None, max_length=255, description="투자 주체")
    target_company_or_fund: Optional[str] = Field(default=None, max_length=255, description="투자 대상")

    # 수치 정보
    investment_amount: Optional[int] = Field(default=None, description="투자·유입 금액 (원 단위)")
    currency: str = Field(default="KRW", max_length=10, description="통화")

    # 확장 정보
    raw_metadata: Optional[dict[str, Any]] = Field(default=None, description="원천 데이터 확장 정보")

    # 시간 정보
    published_at: Optional[datetime] = Field(default=None, description="실제 공시일/기사 발행일")
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="수집 시각")

    model_config = {"str_strip_whitespace": True}
