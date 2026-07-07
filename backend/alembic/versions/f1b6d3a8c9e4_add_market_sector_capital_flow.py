"""vcs.go.kr 업종별 연도별 벤처 신규투자 총액(시장 기준선) 테이블을 추가한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1b6d3a8c9e4"
down_revision: Union[str, None] = "a9d2f7c4e1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_sector_capital_flow",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("vcs_category", sa.String(length=40), nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=True),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_label", sa.String(length=20), nullable=True),
        sa.Column(
            "amount_krw",
            sa.Numeric(precision=20, scale=2),
            nullable=True,
            comment="신규투자 총액(원). 원본 억원 × 1e8",
        ),
        sa.Column("is_total", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "is_partial",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="집계 진행 중 연도",
        ),
        sa.Column(
            "source_type",
            sa.String(length=40),
            nullable=False,
            server_default="VCS_SECTOR_ANNUAL",
        ),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["sector_slug"], ["sectors.slug"], name="fk_market_capital_flow_sector"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vcs_category", "period_year", name="uq_market_capital_flow_natural"
        ),
        comment="vcs.go.kr 업종별 연도별 벤처 신규투자 총액(시장 기준선, 멱등 vcs_category/period_year)",
    )
    op.create_index(
        "ix_market_capital_flow_sector",
        "market_sector_capital_flow",
        ["sector_slug", "period_year"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_capital_flow_sector", table_name="market_sector_capital_flow")
    op.drop_table("market_sector_capital_flow")
