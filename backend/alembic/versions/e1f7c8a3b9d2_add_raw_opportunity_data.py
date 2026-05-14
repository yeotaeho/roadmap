"""Bronze: raw_opportunity_data 테이블 추가 (SMES 사업공고 등 기회 데이터).

Revision ID: e1f7c8a3b9d2
Revises: d4e8f1a2b3c5
Create Date: 2026-05-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e1f7c8a3b9d2"
down_revision: Union[str, None] = "d4e8f1a2b3c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_opportunity_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "source_type",
            sa.String(length=50),
            nullable=False,
            comment="JOB / BOOTCAMP / CONTEST / SMES_* 등",
        ),
        sa.Column(
            "source_url", sa.Text(), nullable=False, comment="원본 공고 링크"
        ),
        sa.Column(
            "raw_title",
            sa.String(length=500),
            nullable=False,
            comment="공고 제목",
        ),
        sa.Column(
            "host_name",
            sa.String(length=150),
            nullable=True,
            comment="주최/주관 기관 또는 기업명",
        ),
        sa.Column(
            "raw_content",
            sa.Text(),
            nullable=True,
            comment="원문 본문 (HTML/CDATA 원형 보존)",
        ),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="지원 자격·상금 규모·근무지·경력 요건 등 부가정보",
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="공고 게시일 (등록일 우선)",
        ),
        sa.Column(
            "deadline_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="지원 마감일시 (앱 알림용)",
        ),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="수집 시각",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_url", name="uq_raw_opportunity_data_source_url"
        ),
        comment="Bronze — 기회(채용·지원사업·부트캠프·공모전) 원천",
    )

    # 마감 임박 알림 쿼리 최적화용 인덱스
    op.create_index(
        "ix_raw_opportunity_deadline_at",
        "raw_opportunity_data",
        ["deadline_at"],
        unique=False,
    )
    op.create_index(
        "ix_raw_opportunity_source_type",
        "raw_opportunity_data",
        ["source_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_raw_opportunity_source_type", table_name="raw_opportunity_data"
    )
    op.drop_index(
        "ix_raw_opportunity_deadline_at", table_name="raw_opportunity_data"
    )
    op.drop_table("raw_opportunity_data")
