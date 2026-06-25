# Silver 리니지 — 한 신호가 가리키는 다수 Bronze 원천(N:M) ORM

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RefinedSignalSources(Base):
    __tablename__ = "refined_signal_sources"
    __table_args__ = (
        UniqueConstraint(
            "signal_id", "raw_table_ref", "raw_id", name="uq_refined_signal_sources_signal_raw"
        ),
        Index("ix_refined_signal_sources_raw", "raw_table_ref", "raw_id"),
        {"comment": "Silver 리니지 — 한 신호가 가리키는 다수 Bronze 원천(N:M, 결함 B)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    signal_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "refined_innovation_signal.id",
            name="fk_refined_signal_sources_signal",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    raw_table_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contribution_weight: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="시차/신뢰 가중(lead-lag)"
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
