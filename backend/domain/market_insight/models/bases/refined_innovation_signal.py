# Silver — 섹터별 교차융합 혁신/자본/담론 신호(엔티티·키워드 추출 적재처) ORM

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RefinedInnovationSignal(Base):
    __tablename__ = "refined_innovation_signal"
    __table_args__ = (
        CheckConstraint(
            "reference_period_end >= reference_period_start", name="ck_refined_innov_period"
        ),
        Index("ix_refined_innov_sector", "sector_slug"),
        Index("ix_refined_innov_data_role", "data_role"),
        Index("ix_refined_innov_period", "reference_period_start", "reference_period_end"),
        # 멱등 자연키 (c3e7f1a9b5d2 보강).
        Index(
            "uq_refined_innov_natural",
            "sector_slug",
            "data_role",
            "signal_topic",
            "reference_period_start",
            "reference_period_end",
            unique=True,
        ),
        {"comment": "Silver — 섹터별 혁신 모멘텀 신호 (data_role·기준기간 1급화: 결함 C·D)"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    sector_slug: Mapped[str] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_refined_innov_sector"), nullable=False
    )
    sub_sector_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("sub_sectors.id", name="fk_refined_innov_sub_sector"),
        nullable=True,
    )
    data_role: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="신호 종류 — CAPITAL_FLOW_SIGNAL / DISCOURSE_SIGNAL 등"
    )
    signal_topic: Mapped[str] = mapped_column(String(255), nullable=False, comment="통합 토픽/기술명")
    momentum_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    extracted_keywords: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="추출 키워드 배열")
    reference_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    reference_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    source_count: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False, comment="교차 출처 보강 개수"
    )
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
