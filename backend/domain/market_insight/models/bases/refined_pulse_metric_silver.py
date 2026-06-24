# Silver — 섹터×일자 정규화 Pulse 시계열을 저장하는 ORM 모델

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


class RefinedPulseMetricSilver(Base):
    __tablename__ = "refined_pulse_metric_silver"
    __table_args__ = (
        CheckConstraint(
            "normalized_score BETWEEN 0 AND 100", name="ck_refined_pulse_silver_score"
        ),
        Index(
            "ix_refined_pulse_silver_sector_date",
            "sector_slug",
            text("reference_date DESC"),
        ),
        Index(
            "uq_refined_pulse_silver_natural",
            "sector_slug",
            text("COALESCE(sub_sector_id, -1)"),
            "reference_date",
            "baseline_method",
            unique=True,
        ),
        {"comment": "Silver — 섹터×일자 정규화 Pulse 시계열 (Gold pulse_metrics_log 입력, 멱등)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_refined_pulse_silver_sector"), nullable=False
    )
    sub_sector_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("sub_sectors.id", name="fk_refined_pulse_silver_sub_sector"),
        nullable=True,
    )
    reference_date: Mapped[date] = mapped_column(Date, nullable=False, comment="일자 그레인")
    raw_signal_value: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6), nullable=True, comment="정규화 전 합성 신호값"
    )
    normalized_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="0~100 정규화 점수"
    )
    momentum_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True, comment="기준 윈도우 대비 변화율(%)"
    )
    status_badge: Mapped[str | None] = mapped_column(String(20), nullable=True)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, comment="모멘텀 윈도우(일)")
    baseline_method: Mapped[str] = mapped_column(
        String(40), nullable=False, comment="zscore / pct_change / ma_ratio"
    )
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
