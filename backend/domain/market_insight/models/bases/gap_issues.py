# Gold — Gap 탭 카드(세상의 문제 ↔ 청년의 기회) ORM

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


class GapIssues(Base):
    __tablename__ = "gap_issues"
    __table_args__ = (
        Index("ix_gap_issues_sector", "sector_slug"),
        {"comment": "Gold — Gap 탭 카드 (세상의 문제 ↔ 청년의 기회, 멱등 재생성)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_gap_issues_sector"), nullable=False
    )
    problem_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    chance_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    detail_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    stakeholders: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    next_actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    published_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
