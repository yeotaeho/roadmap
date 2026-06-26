# Silver — 투자 뉴스에서 추출한 투자 금액(자본 흐름 강도) 적재처 ORM

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RefinedInvestmentFlows(Base):
    __tablename__ = "refined_investment_flows"
    __table_args__ = (
        Index(
            "uq_refined_investment_natural",
            "raw_table_ref",
            "raw_id",
            "prompt_version",
            unique=True,
        ),
        Index("ix_refined_investment_sector", "sector_slug"),
        Index("ix_refined_investment_date", "reference_date"),
        {"comment": "Silver — 투자 뉴스 금액 추출(자본 흐름 강도), 멱등 raw_id/prompt_version"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 섹터는 refined_text_sector_class 조인으로 도출(LLM 강제분류 금지) — 직접 저장 시 nullable.
    sector_slug: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_refined_investment_sector"), nullable=True
    )
    amount_krw: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    series: Mapped[str | None] = mapped_column(String(40), nullable=True)
    company: Mapped[str | None] = mapped_column(String(150), nullable=True)
    reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    raw_table_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
