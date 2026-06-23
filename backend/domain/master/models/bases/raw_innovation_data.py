"""Bronze 혁신 원천 데이터를 저장하는 ORM 모델."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RawInnovationData(Base):
    __tablename__ = "raw_innovation_data"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_raw_innovation_data_source_url"),
        Index(
            "ix_raw_innovation_source_type_published_at",
            "source_type",
            "published_at",
        ),
        {"comment": "Bronze — 특허·논문·오픈소스 등 혁신 흐름 원천"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author_or_assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    abstract_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
