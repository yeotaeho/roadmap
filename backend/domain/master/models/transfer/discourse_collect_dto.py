"""담론(Discourse) Bronze 수집 결과 DTO (Collector → Service → Repository)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class DiscourseCollectDto(BaseModel):
    source_type: str = Field(
        ..., max_length=50, description="예: DISCOURSE_NEWS_RSS, DISCOURSE_GOV_REPORT"
    )
    source_url: Optional[str] = Field(
        default=None, description="뉴스·게시글 링크 (중복 체크 키)"
    )

    # 핵심 엔티티 정보
    headline: str = Field(..., max_length=500, description="헤드라인 / 게시글 제목")
    author_or_publisher: Optional[str] = Field(
        default=None, max_length=255, description="언론사명 / 작성자 / 발간 기관"
    )
    content_body: Optional[str] = Field(
        default=None, description="본문 전문/요약 (HTML 원형 보존)"
    )

    # 확장 정보
    raw_metadata: Optional[dict[str, Any]] = Field(
        default=None, description="카테고리·감성 점수 등 부가정보"
    )

    # 시간 정보
    published_at: Optional[datetime] = Field(
        default=None, description="기사 송고·게시 시각 / 발간일"
    )
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="수집 시각"
    )

    model_config = {"str_strip_whitespace": True}
