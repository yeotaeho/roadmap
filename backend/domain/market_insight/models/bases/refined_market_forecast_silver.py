# Silver — 섹터×기준일 시장 전망(TimesFM 예측) 시계열을 저장하는 ORM 모델

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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RefinedMarketForecastSilver(Base):
    __tablename__ = "refined_market_forecast_silver"
    __table_args__ = (
        CheckConstraint(
            "forecast_score BETWEEN 0 AND 100", name="ck_market_forecast_silver_score"
        ),
        Index(
            "ix_market_forecast_silver_sector_date",
            "sector_slug",
            text("reference_date DESC"),
        ),
        Index(
            "uq_market_forecast_silver_natural",
            "sector_slug",
            "reference_date",
            "horizon_days",
            unique=True,
        ),
        {"comment": "Silver — 섹터×기준일 시장 전망 시계열 (Gold market_forecast_log 입력, 멱등)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("sectors.slug", name="fk_market_forecast_silver_sector"),
        nullable=False,
    )
    reference_date: Mapped[date] = mapped_column(Date, nullable=False, comment="예측 기준일(최신 거래일)")
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, comment="예측 스텝 수(거래일)")
    target_date: Mapped[date] = mapped_column(Date, nullable=False, comment="정보용 라벨(영업일 근사)")
    predicted_return_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="섹터 예측 수익률(%)"
    )
    forecast_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="0~100 전망 점수"
    )
    direction_badge: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True, comment="0~1 신뢰도(분위수 밴드 기반)"
    )
    ticker_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
