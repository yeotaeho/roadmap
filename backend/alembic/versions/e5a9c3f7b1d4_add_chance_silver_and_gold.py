"""Chance Silver(refined_chance_insights)·Gold(chance_opportunities·user_chance_matches)를 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e5a9c3f7b1d4"
down_revision: Union[str, None] = "d4f8a2c6e0b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Silver — opportunity 공고에서 추출한 유형·대상·혜택·자격 ──
    op.create_table(
        "refined_chance_insights",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=True),
        sa.Column("data_role", sa.String(length=50), nullable=False),
        sa.Column("extracted_type", sa.String(length=50), nullable=True),
        sa.Column("extracted_target", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extracted_benefits", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extracted_deadline", sa.Date(), nullable=True),
        sa.Column("extracted_qualifications", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reference_date", sa.Date(), nullable=True),
        sa.Column("raw_table_ref", sa.String(length=50), nullable=False),
        sa.Column("raw_id", sa.BigInteger(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["sector_slug"], ["sectors.slug"], name="fk_refined_chance_sector"),
        comment="Silver — opportunity 공고 추출(유형·대상·혜택·자격, extracted_type NULL = 무귀속)",
    )
    op.create_index(
        "uq_refined_chance_natural",
        "refined_chance_insights",
        ["raw_table_ref", "raw_id", "prompt_version"],
        unique=True,
    )

    # ── Gold — Chance 탭 공고 카드 ──
    op.create_table(
        "chance_opportunities",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("opportunity_type", sa.String(length=50), nullable=True),
        sa.Column("host_name", sa.String(length=150), nullable=True),
        sa.Column("benefit_summary", sa.String(length=255), nullable=True),
        sa.Column("target_audience", sa.String(length=255), nullable=True),
        sa.Column("d_day_date", sa.Date(), nullable=True),
        sa.Column("brief_description", sa.Text(), nullable=True),
        sa.Column("eligibility_checks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("actionable_preps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reference_links", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_table_ref", sa.String(length=50), nullable=True),
        sa.Column("raw_id", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["sector_slug"], ["sectors.slug"], name="fk_chance_opp_sector"),
        comment="Gold — Chance 탭 공고 카드 (raw 리니지로 안정 id 유지, 멱등 upsert)",
    )
    # 안정 id 유지용 자연키(원천 1:1) — user_chance_matches FK 무결성 보존.
    op.create_index(
        "uq_chance_opp_raw", "chance_opportunities", ["raw_table_ref", "raw_id"], unique=True
    )
    op.create_index("ix_chance_opp_sector", "chance_opportunities", ["sector_slug"])

    # ── Gold — 사용자×공고 매칭 ──
    op.create_table(
        "user_chance_matches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", sa.BigInteger(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=True),
        sa.Column("match_reason", sa.String(length=255), nullable=True),
        sa.Column("is_saved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_applied", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_chance_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["chance_opportunities.id"],
            name="fk_user_chance_opp",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "opportunity_id", name="uq_user_chance_user_opp"),
        comment="Gold — 사용자×공고 적합도 매칭(키워드·섹터 기반)",
    )
    op.create_index("ix_user_chance_user", "user_chance_matches", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_chance_user", table_name="user_chance_matches")
    op.drop_table("user_chance_matches")
    op.drop_index("ix_chance_opp_sector", table_name="chance_opportunities")
    op.drop_index("uq_chance_opp_raw", table_name="chance_opportunities")
    op.drop_table("chance_opportunities")
    op.drop_index("uq_refined_chance_natural", table_name="refined_chance_insights")
    op.drop_table("refined_chance_insights")
