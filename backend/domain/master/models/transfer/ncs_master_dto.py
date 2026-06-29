# NCS 역량 마스터 수집 결과 DTO

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class NcsMasterDto(BaseModel):
    source_type: str = Field(..., max_length=50)
    ncs_code: str = Field(..., max_length=30)
    level: int = Field(..., ge=1, le=6)
    name: str = Field(..., max_length=300)
    parent_code: str | None = None

    category_l1_code: str | None = None
    category_l1_name: str | None = None
    category_l2_code: str | None = None
    category_l2_name: str | None = None
    category_l3_code: str | None = None
    category_l3_name: str | None = None
    category_l4_code: str | None = None
    category_l4_name: str | None = None

    description: str | None = None
    performance_criteria: str | None = None
    knowledge_skills: dict[str, Any] | None = None
    linked_qualification: dict[str, Any] | None = None
    raw_metadata: dict[str, Any] | None = None
    version: str | None = None

    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"str_strip_whitespace": True}
