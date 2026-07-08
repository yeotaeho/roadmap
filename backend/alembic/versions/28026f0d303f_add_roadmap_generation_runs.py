"""roadmap_generation_runs 테이블을 추가한다(로드맵 딥 에이전트 생성 런 상태)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "28026f0d303f"
down_revision: Union[str, None] = "f1b6d3a8c9e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roadmap_generation_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="pending", nullable=False),
        sa.Column("trigger", sa.String(length=10), server_default="tab", nullable=False),
        sa.Column("progress", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_roadmap_gen_run_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
        comment="로드맵 딥 에이전트 생성 런 — 사용자당 활성 1개, 진행률 JSONB",
    )
    op.create_index(
        "ix_roadmap_generation_runs_user_id", "roadmap_generation_runs", ["user_id"], unique=False
    )
    op.create_index(
        "uq_roadmap_gen_run_active",
        "roadmap_generation_runs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending','running')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_roadmap_gen_run_active",
        table_name="roadmap_generation_runs",
        postgresql_where=sa.text("status IN ('pending','running')"),
    )
    op.drop_index("ix_roadmap_generation_runs_user_id", table_name="roadmap_generation_runs")
    op.drop_table("roadmap_generation_runs")
