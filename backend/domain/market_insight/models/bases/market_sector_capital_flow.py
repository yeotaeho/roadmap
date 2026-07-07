# 참조 — 벤처투자종합포털(vcs.go.kr) 업종별 연도별 신규투자 총액(시장 기준선) ORM

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class MarketSectorCapitalFlow(Base):
    """vcs.go.kr 업종별 연도별 벤처투자 신규투자 총액(공공저작물). 우리 딜 표본의 커버리지 분모·자금 축 기준선."""

    __tablename__ = "market_sector_capital_flow"
    __table_args__ = (
        UniqueConstraint(
            "vcs_category", "period_year", name="uq_market_capital_flow_natural"
        ),
        Index("ix_market_capital_flow_sector", "sector_slug", "period_year"),
        {"comment": "vcs.go.kr 업종별 연도별 벤처 신규투자 총액(시장 기준선, 멱등 vcs_category/period_year)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 원본 vcs 업종명(ICT서비스·바이오/의료 등). 합계 행은 '합계'.
    vcs_category: Mapped[str] = mapped_column(String(40), nullable=False)
    # 12섹터 매핑 결과 — 애매·미매핑 업종은 NULL(강제 매핑 금지). 합계 행도 NULL.
    sector_slug: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("sectors.slug", name="fk_market_capital_flow_sector"),
        nullable=True,
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # 부분 연도(집계 진행 중) 표기용 — 예 '2026(누적)'.
    period_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount_krw: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True, comment="신규투자 총액(원). 원본 억원 × 1e8"
    )
    is_total: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_partial: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="집계 진행 중 연도"
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="VCS_SECTOR_ANNUAL")
    collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
