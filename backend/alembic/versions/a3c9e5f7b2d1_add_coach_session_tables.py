# 코치 세션·메시지 테이블 신설 (consult 구조 미러 — 추출 컬럼 제외)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a3c9e5f7b2d1"
down_revision = "51f3d7e2ef01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coach_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(120), nullable=True),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column("summarized_until", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        comment="AI 코치 대화 세션 — 재개 가능·롤링 요약",
    )
    op.create_index("ix_coach_sessions_user_id", "coach_sessions", ["user_id"])
    op.create_table(
        "coach_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("coach_sessions.id"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        comment="AI 코치 턴별 메시지(append-only)",
    )
    op.create_index("ix_coach_messages_session_id", "coach_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_coach_messages_session_id", table_name="coach_messages")
    op.drop_table("coach_messages")
    op.drop_index("ix_coach_sessions_user_id", table_name="coach_sessions")
    op.drop_table("coach_sessions")
