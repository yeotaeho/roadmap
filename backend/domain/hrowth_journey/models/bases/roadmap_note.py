# 로드맵 노트 ORM — 마크다운 + [[링크]] 파싱 캐시, 사용자×제목 유니크

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RoadmapNote(Base):
    __tablename__ = "roadmap_notes"
    __table_args__ = (
        UniqueConstraint("user_id", "title", name="uq_roadmap_note_title"),
        {"comment": "로드맵 노트 — 마크다운 + [[링크]] 파싱 캐시"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_roadmap_note_user", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # 저장 시 [[...]] 파싱 결과 캐시 [str] — 백링크 조회용
    linked_titles: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    task_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("planner_tasks.id", name="fk_roadmap_note_task", ondelete="SET NULL"),
        nullable=True,
    )
    quest_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
