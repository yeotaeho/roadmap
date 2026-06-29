# NCS 국가직무능력표준 역량 온톨로지 마스터 (ncs_competency_master)

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class NcsCompetencyMaster(Base):
    __tablename__ = "ncs_competency_master"
    __table_args__ = (
        UniqueConstraint("source_type", "ncs_code", name="uq_ncs_master_source_code"),
        Index("ix_ncs_master_level", "level"),
        Index("ix_ncs_master_parent_code", "parent_code"),
        Index("ix_ncs_master_l1_code", "category_l1_code"),
        {"comment": "NCS 직무-역량 온톨로지 마스터 (정적, UPSERT)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="NCS_CLASSIFICATION / NCS_COMPETENCY_UNIT / NCS_COMPETENCY_ELEMENT",
    )
    ncs_code: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="역량단위코드 또는 분류코드",
    )
    level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="위계 깊이 (1=대분류 ~ 6=능력단위요소)",
    )
    name: Mapped[str] = mapped_column(
        String(300), nullable=False, comment="분류명 또는 역량단위명",
    )
    parent_code: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="상위 ncs_code (L1은 NULL)",
    )

    category_l1_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    category_l1_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_l2_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    category_l2_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_l3_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    category_l3_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_l4_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    category_l4_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="능력단위 정의",
    )
    performance_criteria: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="수행준거",
    )
    knowledge_skills: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="지식·기술·태도 목록",
    )
    linked_qualification: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="연계 자격 정보 (15063879 보충)",
    )
    raw_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="API 원본 부가정보",
    )
    version: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="NCS 버전 (예: v4)",
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )
