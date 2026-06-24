"""담론(raw_discourse_data) 및 검증 기업 마스터(verified_company_master) 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e2c5a7b9d3f4"
down_revision: Union[str, None] = "d7f3a9c1e5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # raw_discourse_data — 뉴스·커뮤니티·보고서 담론 원천
    # ------------------------------------------------------------------
    op.create_table(
        "raw_discourse_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("headline", sa.String(length=500), nullable=False),
        sa.Column("author_or_publisher", sa.String(length=255), nullable=True),
        sa.Column("content_body", sa.Text(), nullable=True),
        sa.Column("raw_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_url", name="uq_raw_discourse_data_source_url"),
        comment="Bronze — 뉴스·커뮤니티·보고서 등 담론(이슈·리스크·기회) 원천",
    )
    op.create_index(
        "ix_raw_discourse_source_type_published_at",
        "raw_discourse_data",
        ["source_type", "published_at"],
    )

    # ------------------------------------------------------------------
    # verified_company_master — 정부 인증·선정 기업 마스터
    # ------------------------------------------------------------------
    op.create_table(
        "verified_company_master",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("business_number", sa.String(length=20), nullable=True),
        sa.Column("corp_number", sa.String(length=20), nullable=True),
        sa.Column("ceo_name", sa.String(length=100), nullable=True),
        sa.Column("certification_type", sa.String(length=100), nullable=True),
        sa.Column("certification_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("certifying_agency", sa.String(length=150), nullable=True),
        sa.Column("industry_sector", sa.String(length=100), nullable=True),
        sa.Column("establishment_date", sa.Date(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("raw_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_file_url", sa.Text(), nullable=True),
        sa.Column("source_file_version", sa.String(length=50), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="정부 인증·선정 기업 마스터 (벤처확인·예비유니콘·이노비즈 등)",
    )
    op.create_index(
        "idx_verified_company_biz_num", "verified_company_master", ["business_number"]
    )
    op.create_index(
        "idx_verified_company_name", "verified_company_master", ["company_name"]
    )
    op.create_index(
        "idx_verified_company_source_type", "verified_company_master", ["source_type"]
    )
    # 부분 UNIQUE — business_number 가 NULL 이 아닌 행에만 (source_type, business_number) 유일.
    op.create_index(
        "uq_verified_company_source_biz",
        "verified_company_master",
        ["source_type", "business_number"],
        unique=True,
        postgresql_where=sa.text("business_number IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_verified_company_source_biz", table_name="verified_company_master"
    )
    op.drop_index(
        "idx_verified_company_source_type", table_name="verified_company_master"
    )
    op.drop_index("idx_verified_company_name", table_name="verified_company_master")
    op.drop_index("idx_verified_company_biz_num", table_name="verified_company_master")
    op.drop_table("verified_company_master")

    op.drop_index(
        "ix_raw_discourse_source_type_published_at", table_name="raw_discourse_data"
    )
    op.drop_table("raw_discourse_data")
