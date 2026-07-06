"""planner_sprints·planner_tasks·roadmap_notes 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e7b3a1c5d9f2"
down_revision: Union[str, None] = "a3c9e5f7b2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 스프린트 — 기간 단위 태스크 묶음 ──
    op.create_table(
        "planner_sprints",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("state", sa.String(length=12), server_default="planned", nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_planner_sprint_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="플래너 스프린트 — 기간 단위 태스크 묶음",
    )
    op.create_index("ix_planner_sprints_user", "planner_sprints", ["user_id"], unique=False)

    # ── 태스크 — sprint_id NULL 이면 백로그 ──
    op.create_table(
        "planner_tasks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sprint_id", sa.BigInteger(), nullable=True),
        sa.Column("quest_key", sa.String(length=60), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=10), server_default="todo", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("estimated_days", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source", sa.String(length=10), server_default="user", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_planner_task_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sprint_id"],
            ["planner_sprints.id"],
            name="fk_planner_task_sprint",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="플래너 태스크 — sprint_id NULL 이면 백로그, quest_key 느슨한 참조",
    )
    op.create_index("ix_planner_tasks_user", "planner_tasks", ["user_id"], unique=False)
    op.create_index("ix_planner_tasks_sprint", "planner_tasks", ["sprint_id"], unique=False)

    # ── 노트 — [[제목]] 링크가 제목으로 해석되므로 사용자×제목 유니크 ──
    op.create_table(
        "roadmap_notes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("linked_titles", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("task_id", sa.BigInteger(), nullable=True),
        sa.Column("quest_key", sa.String(length=60), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_roadmap_note_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["planner_tasks.id"], name="fk_roadmap_note_task", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "title", name="uq_roadmap_note_title"),
        comment="로드맵 노트 — 마크다운 + [[링크]] 파싱 캐시",
    )
    op.create_index("ix_roadmap_notes_user", "roadmap_notes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_roadmap_notes_user", table_name="roadmap_notes")
    op.drop_table("roadmap_notes")
    op.drop_index("ix_planner_tasks_sprint", table_name="planner_tasks")
    op.drop_index("ix_planner_tasks_user", table_name="planner_tasks")
    op.drop_table("planner_tasks")
    op.drop_index("ix_planner_sprints_user", table_name="planner_sprints")
    op.drop_table("planner_sprints")
