# 자기모델 근거(호불호·제약·민감정보) ORM — append-only, content_hash dedup, 민감 격리 플래그

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class UserSelfModelEvidence(Base):
    __tablename__ = "user_self_model_evidence"
    __table_args__ = (
        UniqueConstraint("user_id", "content_hash", name="uq_self_model_evidence_dedup"),
        Index("ix_self_model_evidence_user", "user_id"),
        {"comment": "자기모델 근거 — 대화 추출 호불호·제약·민감정보(append-only, dedup)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_self_model_evidence_user", ondelete="CASCADE"),
        nullable=False,
    )
    dimension: Mapped[str] = mapped_column(String(30), nullable=False)
    polarity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    consult_session_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="coach_extraction"
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
