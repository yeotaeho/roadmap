# 사용자 성향·선호(disposition) ORM — 선택 입력, 임베딩 직렬화 포함(전부 nullable)

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = {"comment": "사용자 성향·선호 — 작업성향·기업규모·근무형태·일의가치(선택 입력)"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_user_preference_user", ondelete="CASCADE"),
        primary_key=True,
    )
    work_style: Mapped[str | None] = mapped_column(String(20), nullable=True)  # stability|challenge|balanced
    company_size_pref: Mapped[str | None] = mapped_column(String(20), nullable=True)  # startup|sme|large|public
    work_type_pref: Mapped[str | None] = mapped_column(String(20), nullable=True)  # office|remote|hybrid
    work_values: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # ["growth","work_life_balance",...]
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user_form")
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
