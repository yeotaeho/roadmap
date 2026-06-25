"""Sync Silver(refined_sync_inputs)·Gold(sync_scores_daily) 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f8c2e6a0d3b7"
down_revision: Union[str, None] = "f6b1d4e8a2c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Silver — 사용자×섹터 적합도/트렌드 입력 ──
    op.create_table(
        "refined_sync_inputs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("affinity_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("trend_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("contributing_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_sync_input_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sector_slug"], ["sectors.slug"], name="fk_sync_input_sector"),
        sa.UniqueConstraint(
            "user_id", "sector_slug", "reference_date", name="uq_sync_input_natural"
        ),
        comment="Silver — 사용자×섹터 적합도(임베딩 코사인)·트렌드(Pulse) 입력",
    )

    # ── Gold — Sync 탭 일별 적합도 점수 ──
    op.create_table(
        "sync_scores_daily",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("recorded_date", sa.Date(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("badge", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_sync_score_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sector_slug"], ["sectors.slug"], name="fk_sync_score_sector"),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="ck_sync_score_range"),
        sa.UniqueConstraint(
            "user_id", "sector_slug", "recorded_date", name="uq_sync_score_natural"
        ),
        comment="Gold — Sync 탭 사용자×섹터 일별 적합도 점수(멱등)",
    )
    op.create_index("ix_sync_scores_user", "sync_scores_daily", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_sync_scores_user", table_name="sync_scores_daily")
    op.drop_table("sync_scores_daily")
    op.drop_table("refined_sync_inputs")
