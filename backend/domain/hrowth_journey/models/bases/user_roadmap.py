# 사용자 전략 로드맵 헤더 ORM — 스킬 트라이앵글·키워드 브릿지 + 퀘스트 트리 루트

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class UserRoadmap(Base):
    __tablename__ = "user_roadmaps"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_roadmap_user"),
        {"comment": "사용자 전략 로드맵 헤더 — 사용자당 1 활성"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_user_roadmap_user", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 스킬 트라이앵글 3축 [{id, label, blurb}]
    skill_pillars: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # 키워드 브릿지 [str]
    bridge_keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
