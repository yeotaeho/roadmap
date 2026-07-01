# 코치 대화 메시지 ORM — 세션별 턴(role·content), append-only

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class CoachMessage(Base):
    __tablename__ = "coach_messages"
    __table_args__ = (
        Index("ix_coach_messages_session", "session_id", "created_at"),
        {"comment": "코치 대화 메시지 — 세션별 턴(user/assistant)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coach_sessions.id", name="fk_coach_message_session", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
