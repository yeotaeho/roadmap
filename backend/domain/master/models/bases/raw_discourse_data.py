# Bronze 담론·정성 원천 데이터를 저장하는 ORM 모델 (뉴스·커뮤니티·보고서)

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RawDiscourseData(Base):
    __tablename__ = "raw_discourse_data"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_raw_discourse_data_source_url"),
        Index(
            "ix_raw_discourse_source_type_published_at",
            "source_type",
            "published_at",
        ),
        {"comment": "Bronze — 뉴스·커뮤니티·보고서 등 담론(이슈·리스크·기회) 원천"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="NEWS / REDDIT / BLIND / REPORT / JOB_INFO 등"
    )
    source_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="뉴스·게시글 링크 또는 출처 URL"
    )

    # 핵심 엔티티 정보
    headline: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="헤드라인 / 게시글 제목 / 직업명"
    )
    author_or_publisher: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="언론사명 / 작성자 / 발간 기관"
    )
    content_body: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="본문 전문/요약 (HTML 원형 보존)"
    )

    # 확장 정보 (Silver 계층 LLM 파싱용)
    raw_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="카테고리·댓글 수·감성 점수 등 부가정보"
    )

    # 시간 정보
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="기사 송고·게시 시각 / 발간일"
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="수집 시각"
    )
