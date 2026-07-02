# 사용자 자기모델(구조 척추) ORM — RIASEC·Big Five·자기서사(코치 추출/폼, 전부 nullable)

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class UserSelfModel(Base):
    __tablename__ = "user_self_model"
    __table_args__ = {
        "comment": "자기모델 구조 척추 — RIASEC·Big Five·자기서사(coach 추출/폼)"
    }

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_user_self_model_user", ondelete="CASCADE"),
        primary_key=True,
    )
    # {"scores": {"R":0-100,"I":..,...}, "top_codes": ["I","A","S"]}
    riasec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {"openness":0-100,"conscientiousness":..,"extraversion":..,"agreeableness":..,"neuroticism":..}
    big_five: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    narrative_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 축별 신뢰도 {"riasec":0.0-1.0, "big_five":..}
    axis_confidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="consult_extraction"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
