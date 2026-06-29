# 기술 채택 미시신호 수집 결과 DTO (npm / PyPI / HuggingFace → raw_tech_adoption_data)

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


EcosystemType = Literal["npm", "pypi", "hf"]


class TechAdoptionCollectDto(BaseModel):
    ecosystem: EcosystemType
    package_name: str = Field(..., max_length=200)
    sector: str = Field(..., max_length=50)
    weekly_downloads: int | None = None
    week_start_date: date
    raw_metadata: dict[str, Any] | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"str_strip_whitespace": True}
