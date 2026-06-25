# Gold — Sync 탭 사용자×섹터 일별 적합도 점수 ORM

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class SyncScoresDaily(Base):
    __tablename__ = "sync_scores_daily"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_sync_score_range"),
        UniqueConstraint("user_id", "sector_slug", "recorded_date", name="uq_sync_score_natural"),
        Index("ix_sync_scores_user", "user_id"),
        {"comment": "Gold — Sync 탭 사용자×섹터 일별 적합도 점수(멱등)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_sync_score_user", ondelete="CASCADE"),
        nullable=False,
    )
    sector_slug: Mapped[str] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_sync_score_sector"), nullable=False
    )
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    badge: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
