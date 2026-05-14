"""Bronze: 기회(Opportunity) 원천 테이블 (`raw_opportunity_data`).

채용/부트캠프/공모전/정부 지원사업 등 사용자에게 '기회'가 되는 공고를 수집한다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RawOpportunityData(Base):
    __tablename__ = "raw_opportunity_data"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_raw_opportunity_data_source_url"),
        {"comment": "Bronze — 기회(채용·지원사업·부트캠프·공모전) 원천"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="JOB / BOOTCAMP / CONTEST / SMES_* 등"
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False, comment="원본 공고 링크")

    # 핵심 엔티티 정보
    raw_title: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="공고 제목"
    )
    host_name: Mapped[str | None] = mapped_column(
        String(150), nullable=True, comment="주최/주관 기관 또는 기업명"
    )
    raw_content: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="원문 본문 (HTML/CDATA 원형 보존)"
    )

    # 확장 정보 (Silver 계층 LLM 파싱용)
    raw_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="지원 자격·상금 규모·근무지·경력 요건 등 부가정보"
    )

    # 시간 정보
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="공고 게시일 (등록일 우선)"
    )
    deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="지원 마감일시 (앱 알림용)"
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="수집 시각",
    )
