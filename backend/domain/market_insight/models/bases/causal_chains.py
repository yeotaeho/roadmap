# Gold — Pulse 인과사슬 카드(거시→산업→청년기회) ORM

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class CausalChains(Base):
    __tablename__ = "causal_chains"
    __table_args__ = (
        Index("ix_causal_chains_sector", "sector_slug"),
        {"comment": "Gold — Pulse 인과사슬 카드 (거시→산업→청년기회)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_causal_chains_sector"), nullable=False
    )
    macro_event: Mapped[str] = mapped_column(String(255), nullable=False)
    industry_impact: Mapped[str] = mapped_column(String(255), nullable=False)
    youth_chance: Mapped[str] = mapped_column(String(255), nullable=False)
    published_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
