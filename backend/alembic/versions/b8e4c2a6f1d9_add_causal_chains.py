"""causal_chains Silver(refined_causal_chain_insights)·Gold(causal_chains) 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b8e4c2a6f1d9"
down_revision: Union[str, None] = "a7d3f1b9c2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Silver — 인과사슬 추출(거시→산업→청년기회), 멱등 raw_id/prompt_version ──
    op.create_table(
        "refined_causal_chain_insights",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("macro_event", sa.String(length=255), nullable=True),
        sa.Column("industry_impact", sa.String(length=255), nullable=True),
        sa.Column("youth_chance", sa.String(length=255), nullable=True),
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
            ["sector_slug"], ["sectors.slug"], name="fk_refined_causal_sector"
        ),
        comment="Silver — 인과사슬(거시→산업→청년기회) 추출 (멱등 raw_id/prompt_version)",
    )
    op.create_index(
        "uq_refined_causal_natural",
        "refined_causal_chain_insights",
        ["raw_table_ref", "raw_id", "prompt_version"],
        unique=True,
    )
    op.create_index(
        "ix_refined_causal_sector", "refined_causal_chain_insights", ["sector_slug"]
    )

    # ── Gold — Pulse 인과사슬 카드 ──
    op.create_table(
        "causal_chains",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("macro_event", sa.String(length=255), nullable=False),
        sa.Column("industry_impact", sa.String(length=255), nullable=False),
        sa.Column("youth_chance", sa.String(length=255), nullable=False),
        sa.Column("published_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["sector_slug"], ["sectors.slug"], name="fk_causal_chains_sector"
        ),
        comment="Gold — Pulse 인과사슬 카드 (거시→산업→청년기회)",
    )
    op.create_index("ix_causal_chains_sector", "causal_chains", ["sector_slug"])


def downgrade() -> None:
    op.drop_index("ix_causal_chains_sector", table_name="causal_chains")
    op.drop_table("causal_chains")
    op.drop_index("ix_refined_causal_sector", table_name="refined_causal_chain_insights")
    op.drop_index("uq_refined_causal_natural", table_name="refined_causal_chain_insights")
    op.drop_table("refined_causal_chain_insights")
