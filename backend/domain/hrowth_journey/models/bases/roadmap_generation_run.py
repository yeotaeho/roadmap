# 로드맵 생성 런 ORM — 사용자당 활성(pending/running) 1개, 진행률·결과 JSONB 기록
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RoadmapGenerationRun(Base):
    __tablename__ = "roadmap_generation_runs"
    __table_args__ = (
        Index(
            "uq_roadmap_gen_run_active",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('pending','running')"),
        ),
        {"comment": "로드맵 딥 에이전트 생성 런 — 사용자당 활성 1개, 진행률 JSONB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_roadmap_gen_run_user", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # pending | running | succeeded | failed
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="pending")
    # tab | coach
    trigger: Mapped[str] = mapped_column(String(10), nullable=False, server_default="tab")
    progress: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
