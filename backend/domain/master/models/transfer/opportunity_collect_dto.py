"""기회(Opportunity) Bronze 수집 결과 DTO (Collector → Service → Repository)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class OpportunityCollectDto(BaseModel):
    source_type: str = Field(
        ...,
        max_length=50,
        description="예: SMES_STARTUP, SMES_RND, SMES_EXPORT, SMES_SCALE_UP, SMES_GRANT",
    )
    source_url: str = Field(
        ..., description="원본 공고 링크 (NOT NULL, 중복 체크 키)"
    )

    # 핵심 엔티티 정보
    raw_title: str = Field(..., max_length=500, description="공고 제목 (필수)")
    host_name: Optional[str] = Field(
        default=None, max_length=150, description="주최/주관 기관"
    )
    raw_content: Optional[str] = Field(
        default=None, description="원문 본문 (HTML·CDATA 원형 그대로 보존)"
    )

    # 확장 정보
    raw_metadata: Optional[dict[str, Any]] = Field(
        default=None, description="지원 자격·상금·근무지 등 부가정보"
    )

    # 시간 정보
    published_at: Optional[datetime] = Field(
        default=None, description="공고 게시일 (등록일 우선)"
    )
    deadline_at: Optional[datetime] = Field(
        default=None, description="지원 마감일시"
    )
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="수집 시각",
    )

    model_config = {"str_strip_whitespace": True}
