# Silver — raw 자유 텍스트의 LLM 섹터 분류 결과를 저장하는 ORM 모델

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RefinedTextSectorClass(Base):
    __tablename__ = "refined_text_sector_class"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence BETWEEN 0 AND 1)",
            name="ck_refined_text_sector_confidence",
        ),
        CheckConstraint(
            "sentiment IS NULL OR sentiment IN ('긍정', '중립', '부정')",
            name="ck_refined_text_sector_sentiment_enum",
        ),
        CheckConstraint(
            "sentiment_score IS NULL OR (sentiment_score BETWEEN -1 AND 1)",
            name="ck_refined_text_sector_sentiment_score",
        ),
        # 멱등 재처리용 자연키 (raw 행 × 프롬프트 버전).
        Index(
            "uq_refined_text_sector_natural",
            "raw_table_ref",
            "raw_id",
            "prompt_version",
            unique=True,
        ),
        # 축 집계 조회 가속.
        Index(
            "ix_refined_text_sector_lookup",
            "raw_table_ref",
            "sector_slug",
            "confidence",
        ),
        {"comment": "Silver — raw 자유 텍스트 LLM 섹터 분류(economic_text·discourse 축 입력, 멱등)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    raw_table_ref: Mapped[str] = mapped_column(
        String(40), nullable=False, comment="원천 테이블명(raw_economic_data 등)"
    )
    raw_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="원천 행 PK(리니지)")
    sector_slug: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("sectors.slug", name="fk_refined_text_sector_sector"),
        nullable=True,
        comment="LLM 분류 섹터. 무귀속이면 NULL(강제 매핑 금지)",
    )
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3), nullable=True, comment="0~1 분류 신뢰도"
    )
    sentiment: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="LLM 감성 판정 '긍정'/'중립'/'부정'. 무판정이면 NULL"
    )
    sentiment_score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True, comment="감성 점수 -1.0(부정)~1.0(긍정). Pulse 점수 가산 이동 입력"
    )
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str] = mapped_column(
        String(40), nullable=False, comment="프롬프트·파서 버전(자연키)"
    )
    input_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="분류 입력 텍스트 sha256"
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
