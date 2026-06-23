"""사람·역량 Bronze 수집 결과를 전달하는 Pydantic DTO."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class PeopleCollectDto(BaseModel):
    source_type: str = Field(..., max_length=50)
    source_url: str | None = None
    keyword_or_job: str = Field(..., max_length=100)
    search_volume_or_count: int | None = None
    raw_metadata: dict[str, Any] | None = None
    reference_date: date | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"str_strip_whitespace": True}

