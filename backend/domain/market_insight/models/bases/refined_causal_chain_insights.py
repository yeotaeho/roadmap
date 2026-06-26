# Silver — 거시→산업→청년기회 인과사슬 추출 적재처 ORM

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RefinedCausalChainInsights(Base):
    __tablename__ = "refined_causal_chain_insights"
    __table_args__ = (
        Index(
            "uq_refined_causal_natural",
            "raw_table_ref",
            "raw_id",
            "prompt_version",
            unique=True,
        ),
        Index("ix_refined_causal_sector", "sector_slug"),
        {"comment": "Silver — 인과사슬(거시→산업→청년기회) 추출 (멱등 raw_id/prompt_version)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_refined_causal_sector"), nullable=False
    )
    macro_event: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry_impact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    youth_chance: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    raw_table_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
