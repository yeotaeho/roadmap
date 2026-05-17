"""시장 시계열 Bronze DTO (Collector → Service → Repository)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class MarketTimeseriesDto(BaseModel):
    ticker: str = Field(..., max_length=32)
    trade_date: date = Field(..., description="거래일(시장 기준)")
    source_type: str = Field(..., max_length=50)
    asset_name: str = Field(..., max_length=255)
    theme: Optional[str] = Field(default=None, max_length=100)
    currency: str = Field(default="KRW", max_length=10)

    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: float
    volume: int = Field(..., ge=0)
    turnover_amount: Optional[int] = Field(default=None, description="추정 거래대금")

    raw_metadata: Optional[dict[str, Any]] = None
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="수집 시각",
    )

    model_config = {"str_strip_whitespace": True}
