# 상담 대화 세션 ORM — 명시적 세션·롤링 요약·추출 표시

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class ConsultSession(Base):
    __tablename__ = "consult_sessions"
    __table_args__ = (
        Index("ix_consult_sessions_user", "user_id"),
        {"comment": "상담 대화 세션 — 명시적 세션·롤링 요약·추출 표시"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_consult_session_user", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="active")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summarized_until: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    extracted_until: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
