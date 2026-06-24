# 정부 인증·선정 기업 마스터를 저장하는 ORM 모델 (verified_company_master)

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class VerifiedCompanyMaster(Base):
    __tablename__ = "verified_company_master"
    __table_args__ = (
        Index("idx_verified_company_biz_num", "business_number"),
        Index("idx_verified_company_name", "company_name"),
        Index("idx_verified_company_source_type", "source_type"),
        # 동일 출처(source_type)에서 동일 사업자번호는 1개만 (갱신 시 UPDATE).
        # business_number 가 NULL 인 행은 제약 대상에서 제외.
        Index(
            "uq_verified_company_source_biz",
            "source_type",
            "business_number",
            unique=True,
            postgresql_where=text("business_number IS NOT NULL"),
        ),
        {"comment": "정부 인증·선정 기업 마스터 (벤처확인·예비유니콘·이노비즈 등)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="VENTURE_CERTIFIED / KSTARTUP_PREUNICORN / INNOBIZ 등"
    )

    # 핵심 식별 정보
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="기업명")
    business_number: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="사업자등록번호(10자리)"
    )
    corp_number: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="법인등록번호(13자리)"
    )
    ceo_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="대표자명")

    # 인증/선정 정보
    certification_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="인증·선정 명칭 (예: 벤처기업 인증)"
    )
    certification_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="인증일자 또는 선정 발표일"
    )
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="인증 만료일")
    certifying_agency: Mapped[str | None] = mapped_column(
        String(150), nullable=True, comment="인증·선정 기관"
    )

    # 기업 세부 정보
    industry_sector: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="업종·분야"
    )
    establishment_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="설립일")
    address: Mapped[str | None] = mapped_column(Text, nullable=True, comment="주소")

    # 확장 정보
    raw_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="원천 파일의 추가 필드"
    )

    # 데이터 출처 정보
    source_file_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="원본 파일 다운로드 URL"
    )
    source_file_version: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="파일 버전·배포 년월 (예: 2026-04)"
    )

    # 시간 정보
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="최초 수집 시각"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="갱신 시각 (재수집 시 덮어쓰기)",
    )
