"""혁신 Bronze 수집 결과를 전달하는 Pydantic DTO."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class InnovationCollectDto(BaseModel):
    source_type: str = Field(..., max_length=50)
    source_url: str | None = None
    title: str = Field(..., max_length=500)
    author_or_assignee: str | None = Field(default=None, max_length=255)
    abstract_text: str | None = None
    raw_metadata: dict[str, Any] | None = None
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"str_strip_whitespace": True}

