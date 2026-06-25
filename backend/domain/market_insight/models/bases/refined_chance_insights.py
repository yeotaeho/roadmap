# Silver — opportunity 공고에서 추출한 유형·대상·혜택·자격 ORM

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RefinedChanceInsights(Base):
    __tablename__ = "refined_chance_insights"
    __table_args__ = (
        Index("uq_refined_chance_natural", "raw_table_ref", "raw_id", "prompt_version", unique=True),
        {"comment": "Silver — opportunity 공고 추출(유형·대상·혜택·자격, extracted_type NULL = 무귀속)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_refined_chance_sector"), nullable=True
    )
    data_role: Mapped[str] = mapped_column(String(50), nullable=False)
    extracted_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extracted_target: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extracted_benefits: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extracted_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    extracted_qualifications: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    raw_table_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
