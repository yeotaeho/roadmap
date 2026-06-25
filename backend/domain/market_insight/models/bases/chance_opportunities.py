# Gold — Chance 탭 공고 카드 ORM

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class ChanceOpportunities(Base):
    __tablename__ = "chance_opportunities"
    __table_args__ = (
        Index("uq_chance_opp_raw", "raw_table_ref", "raw_id", unique=True),
        Index("ix_chance_opp_sector", "sector_slug"),
        {"comment": "Gold — Chance 탭 공고 카드 (raw 리니지로 안정 id 유지, 멱등 upsert)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_chance_opp_sector"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    opportunity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    host_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    benefit_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_audience: Mapped[str | None] = mapped_column(String(255), nullable=True)
    d_day_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    brief_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    eligibility_checks: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    actionable_preps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reference_links: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_table_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
