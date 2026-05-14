"""Bronze: raw_economic_data 테이블 추가."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e9b2a1f4d0"
down_revision: Union[str, None] = "9f2a6d4e1b0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_economic_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False, comment="DART, WOWTALE 등"),
        sa.Column("source_url", sa.String(length=255), nullable=True, comment="원문/출처 URL"),
        sa.Column(
            "target_company_or_fund",
            sa.String(length=100),
            nullable=True,
            comment="투자 대상 기업·펀드",
        ),
        sa.Column("investment_amount", sa.BigInteger(), nullable=True, comment="투자·유입 금액(원)"),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="수집 시각",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Bronze — 경제·투자 원천",
    )
    op.create_index(
        "ix_raw_economic_source_type_url",
        "raw_economic_data",
        ["source_type", "source_url"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_raw_economic_source_type_url", table_name="raw_economic_data")
    op.drop_table("raw_economic_data")
