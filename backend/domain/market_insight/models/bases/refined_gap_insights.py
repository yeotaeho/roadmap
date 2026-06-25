# Silver — discourse 본문에서 추출한 미해결 문제·청년 기회 ORM

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RefinedGapInsights(Base):
    __tablename__ = "refined_gap_insights"
    __table_args__ = (
        Index("uq_refined_gap_natural", "raw_table_ref", "raw_id", "prompt_version", unique=True),
        Index("ix_refined_gap_sector", "sector_slug"),
        {"comment": "Silver — discourse 추출 미해결 문제·기회 (extracted_problem NULL = 무귀속 처리됨)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_refined_gap_sector"), nullable=False
    )
    data_role: Mapped[str] = mapped_column(String(50), nullable=False)
    extracted_problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_opportunity: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    stakeholders: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    next_actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    raw_table_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
