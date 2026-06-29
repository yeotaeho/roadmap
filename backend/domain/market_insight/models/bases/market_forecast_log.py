# Gold — 시장 전망 탭 섹터별 기준일 예측 점수를 저장하는 ORM 모델

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class MarketForecastLog(Base):
    __tablename__ = "market_forecast_log"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_market_forecast_log_score"),
        Index("idx_market_forecast_date_sector", "forecast_date", "sector_slug"),
        Index(
            "uq_market_forecast_log_natural",
            "sector_slug",
            "forecast_date",
            "horizon_days",
            unique=True,
        ),
        {"comment": "Gold — 시장 전망 섹터별 기준일 예측 점수 (멱등 재생성)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("sectors.slug", name="fk_market_forecast_log_sector"),
        nullable=False,
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, comment="예측 기준일")
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="0~100 전망 점수")
    direction_badge: Mapped[str] = mapped_column(String(20), nullable=False)
    predicted_return_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
