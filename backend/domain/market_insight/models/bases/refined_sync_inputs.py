# Silver — 사용자×섹터 적합도(임베딩 코사인)·트렌드(Pulse) 입력 ORM

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RefinedSyncInputs(Base):
    __tablename__ = "refined_sync_inputs"
    __table_args__ = (
        UniqueConstraint("user_id", "sector_slug", "reference_date", name="uq_sync_input_natural"),
        {"comment": "Silver — 사용자×섹터 적합도(임베딩 코사인)·트렌드(Pulse) 입력"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_sync_input_user", ondelete="CASCADE"),
        nullable=False,
    )
    sector_slug: Mapped[str] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_sync_input_sector"), nullable=False
    )
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    affinity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    trend_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    contributing_keywords: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
