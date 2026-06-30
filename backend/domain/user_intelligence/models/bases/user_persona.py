# 사용자 페르소나(스킬·경험·학력) ORM — coach 상담이 작성, Roadmap·Sync가 읽음

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class UserPersona(Base):
    __tablename__ = "user_personas"
    __table_args__ = {"comment": "사용자 페르소나 — 상담에서 도출된 스킬·경험·학력(coach 작성)"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_user_persona_user", ondelete="CASCADE"),
        primary_key=True,
    )
    # [{school, major, degree, status}]
    education: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [{title, description, period}]
    experiences: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [{name, level: 입문|중급|심화}]
    skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 스펙 심화(전부 nullable) — Phase 1 확장
    # [{name, issuer, year}]
    certifications: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [{language, test, score}]
    languages: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [{type: github|portfolio|blog, url}]
    links: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [{title, description, role, period, tech_stack: [str]}]
    projects: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="mock")
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
