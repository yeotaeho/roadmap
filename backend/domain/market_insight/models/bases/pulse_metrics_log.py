# Gold — Pulse 탭 섹터별 일별 트렌드 점수를 저장하는 ORM 모델

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


class PulseMetricsLog(Base):
    __tablename__ = "pulse_metrics_log"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_pulse_metrics_score"),
        Index("idx_pulse_metrics_date_sector", "recorded_date", "sector_slug"),
        Index(
            "uq_pulse_metrics_natural",
            "sector_slug",
            text("COALESCE(sub_sector_id, -1)"),
            "recorded_date",
            unique=True,
        ),
        {"comment": "Gold — Pulse 탭 섹터별 일별 트렌드 점수 (멱등 재생성)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_pulse_metrics_sector"), nullable=False
    )
    sub_sector_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sub_sectors.id", name="fk_pulse_metrics_sub_sector"), nullable=True
    )
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False, comment="차트 X축 날짜")
    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="0~100 트렌드 점수")
    status_badge: Mapped[str] = mapped_column(String(20), nullable=False, comment="태풍급/급상승 등")
    momentum_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True, comment="증감률(%)"
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
