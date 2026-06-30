# 사용자 기본정보(데모그래픽) ORM — 온보딩·프로필에서 선택 입력(전부 nullable, 임베딩 제외)

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = {"comment": "사용자 기본정보(데모그래픽) — 선택 입력, 임베딩 직렬화 제외"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_user_profile_user", ondelete="CASCADE"),
        primary_key=True,
    )
    birth_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)  # male|female|other
    region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # student|job_seeking|employed|career_switch
    education_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # high_school|undergrad|bachelor|master|phd
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user_form")
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
