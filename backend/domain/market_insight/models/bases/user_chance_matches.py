# Gold — 사용자×공고 적합도 매칭(키워드·섹터 기반) ORM

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class UserChanceMatches(Base):
    __tablename__ = "user_chance_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="uq_user_chance_user_opp"),
        Index("ix_user_chance_user", "user_id"),
        {"comment": "Gold — 사용자×공고 적합도 매칭(키워드·섹터 기반)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_user_chance_user", ondelete="CASCADE"),
        nullable=False,
    )
    opportunity_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chance_opportunities.id", name="fk_user_chance_opp", ondelete="CASCADE"),
        nullable=False,
    )
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_saved: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    is_applied: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
