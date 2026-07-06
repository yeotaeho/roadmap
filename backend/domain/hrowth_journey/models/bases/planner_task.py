# 플래너 태스크 ORM — sprint_id NULL 이면 백로그, quest_key 느슨한 참조

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class PlannerTask(Base):
    __tablename__ = "planner_tasks"
    __table_args__ = (
        {"comment": "플래너 태스크 — sprint_id NULL 이면 백로그, quest_key 느슨한 참조"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_planner_task_user", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sprint_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("planner_sprints.id", name="fk_planner_task_sprint", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quest_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # todo | doing | done
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="todo")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # user | ai
    source: Mapped[str] = mapped_column(String(10), nullable=False, server_default="user")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
