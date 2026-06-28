"""user_personas + roadmap(user_roadmaps·roadmap_quests·growth_logs) 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "c4e7a9d2f6b1"
down_revision: Union[str, None] = "d7a1f3c9e2b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 페르소나 — user_intelligence 소유(coach 작성, Roadmap·Sync 읽음) ──
    op.create_table(
        "user_personas",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("education", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("experiences", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=30), server_default="mock", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_persona_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
        comment="사용자 페르소나 — 상담에서 도출된 스킬·경험·학력(coach 작성)",
    )

    # ── 로드맵 헤더 — hrowth_journey 소유(사용자당 1 활성) ──
    op.create_table(
        "user_roadmaps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("skill_pillars", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bridge_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_roadmap_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_roadmap_user"),
        comment="사용자 전략 로드맵 헤더 — 사용자당 1 활성",
    )

    # ── 퀘스트 트리 노드 — parent_key 자기참조 ──
    op.create_table(
        "roadmap_quests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("roadmap_id", sa.BigInteger(), nullable=False),
        sa.Column("quest_key", sa.String(length=60), nullable=False),
        sa.Column("parent_key", sa.String(length=60), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=10), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("state", sa.String(length=12), server_default="available", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["roadmap_id"],
            ["user_roadmaps.id"],
            name="fk_roadmap_quest_roadmap",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("roadmap_id", "quest_key", name="uq_roadmap_quest_key"),
        comment="로드맵 퀘스트 트리 노드 — parent_key 자기참조",
    )
    op.create_index("ix_roadmap_quests_roadmap", "roadmap_quests", ["roadmap_id"], unique=False)

    # ── 성장 아카이브 일별 로그 — 사용자×날짜 멱등 ──
    op.create_table(
        "growth_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "completed_quest_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_growth_log_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "log_date", name="uq_growth_log_natural"),
        comment="성장 아카이브 일별 로그 — 사용자×날짜 멱등",
    )
    op.create_index("ix_growth_logs_user", "growth_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_growth_logs_user", table_name="growth_logs")
    op.drop_table("growth_logs")
    op.drop_index("ix_roadmap_quests_roadmap", table_name="roadmap_quests")
    op.drop_table("roadmap_quests")
    op.drop_table("user_roadmaps")
    op.drop_table("user_personas")
