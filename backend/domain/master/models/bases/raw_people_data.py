"""Bronze 사람·역량 수요 원천 데이터를 저장하는 ORM 모델."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RawPeopleData(Base):
    __tablename__ = "raw_people_data"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "keyword_or_job",
            "reference_date",
            name="uq_raw_people_data_source_keyword_date",
        ),
        Index(
            "ix_raw_people_source_type_reference_date",
            "source_type",
            "reference_date",
        ),
        {"comment": "Bronze — 검색량·채용·훈련 수요 등 사람·역량 수요 원천"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    keyword_or_job: Mapped[str] = mapped_column(String(100), nullable=False)
    search_volume_or_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
