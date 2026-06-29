# 기술 채택 미시신호 Bronze 테이블 — npm/PyPI/HuggingFace 주간 다운로드·트렌딩 스냅샷

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RawTechAdoptionData(Base):
    __tablename__ = "raw_tech_adoption_data"
    __table_args__ = (
        UniqueConstraint(
            "ecosystem", "package_name", "week_start_date",
            name="uq_raw_tech_adoption_ecosystem_pkg_week",
        ),
        Index("ix_raw_tech_adoption_ecosystem_week", "ecosystem", "week_start_date"),
        Index("ix_raw_tech_adoption_sector_week", "sector", "week_start_date"),
        {"comment": "Bronze — npm/PyPI/HuggingFace 기술 채택 주간 스냅샷"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    ecosystem: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="npm | pypi | hf",
    )
    package_name: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="패키지명 또는 HuggingFace 모델 ID",
    )
    sector: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="FRONTEND / AI_ML / DEVOPS / MOBILE / STYLING / BACKEND 등",
    )
    weekly_downloads: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="주간 다운로드 수 (HF trending은 NULL 가능)",
    )
    week_start_date: Mapped[datetime] = mapped_column(
        Date, nullable=False,
        comment="해당 주 월요일 (ISO 8601 기준)",
    )

    raw_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="부가정보: hf={downloads_alltime, trending_rank, pipeline_tag}, npm={detail_url}",
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
