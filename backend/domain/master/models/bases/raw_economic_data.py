"""Bronze: 경제/자본 흐름 원천 테이블 (`raw_economic_data`)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RawEconomicData(Base):
    __tablename__ = "raw_economic_data"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_raw_economic_data_source_url"),
        {"comment": "Bronze — 경제·투자·예산 등 자본 흐름 원천"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    source_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="DART_API, VC_NEWS 등")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True, comment="원문/출처 URL")

    # 핵심 엔티티 정보
    raw_title: Mapped[str] = mapped_column(String(500), nullable=False, comment="공시 제목, 뉴스 헤드라인")
    investor_name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="투자 주체")
    target_company_or_fund: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="투자 대상 기업·펀드"
    )

    # 수치 정보
    investment_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="투자·유입 금액(원)")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, server_default="KRW", comment="통화")

    # 확장 정보
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="원천 데이터 확장 정보")

    # 시간 정보
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="실제 공시일/기사 발행일"
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="수집 시각",
    )
