"""refined_investment_flows Silver 테이블을 생성한다(투자 뉴스 금액 추출)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c5f9a3b7d1e2"
down_revision: Union[str, None] = "b8e4c2a6f1d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Silver — 투자 뉴스 금액 추출(자본 흐름 강도), 멱등 raw_id/prompt_version ──
    op.create_table(
        "refined_investment_flows",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=True),
        sa.Column("amount_krw", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=True),
        sa.Column("series", sa.String(length=40), nullable=True),
        sa.Column("company", sa.String(length=150), nullable=True),
        sa.Column("reference_date", sa.Date(), nullable=True),
        sa.Column("raw_table_ref", sa.String(length=50), nullable=False),
        sa.Column("raw_id", sa.BigInteger(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["sector_slug"], ["sectors.slug"], name="fk_refined_investment_sector"
        ),
        comment="Silver — 투자 뉴스 금액 추출(자본 흐름 강도), 멱등 raw_id/prompt_version",
    )
    op.create_index(
        "uq_refined_investment_natural",
        "refined_investment_flows",
        ["raw_table_ref", "raw_id", "prompt_version"],
        unique=True,
    )
    op.create_index(
        "ix_refined_investment_sector", "refined_investment_flows", ["sector_slug"]
    )
    op.create_index(
        "ix_refined_investment_date", "refined_investment_flows", ["reference_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_refined_investment_date", table_name="refined_investment_flows")
    op.drop_index("ix_refined_investment_sector", table_name="refined_investment_flows")
    op.drop_index("uq_refined_investment_natural", table_name="refined_investment_flows")
    op.drop_table("refined_investment_flows")
