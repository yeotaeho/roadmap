# Gold — Pulse 3줄 경제 브리핑(청년 진로 관점) ORM

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class EconomicBriefing(Base):
    __tablename__ = "economic_briefings"
    __table_args__ = (
        CheckConstraint("line_number IN (1, 2, 3)", name="ck_briefing_line_number"),
        Index("uq_economic_briefings_natural", "published_date", "line_number", unique=True),
        Index("idx_economic_briefings_date", "published_date"),
        {"comment": "Gold — Pulse 3줄 경제 브리핑 (일자×줄번호 멱등)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    published_date: Mapped[date] = mapped_column(Date, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(String(255), nullable=False)
    trend_icon: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="UP_RIGHT / DOWN_RIGHT / WAVE"
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
