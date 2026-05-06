"""Reset schema to users and user_sync_profiles only.

Revision ID: 9f2a6d4e1b0c
Revises: 553c40c8a4c7
Create Date: 2026-05-06 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9f2a6d4e1b0c"
down_revision: Union[str, None] = "553c40c8a4c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_all_public_tables_except_alembic_version() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename <> 'alembic_version'
            """
        )
    ).fetchall()
    for (table_name,) in rows:
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))


def upgrade() -> None:
    _drop_all_public_tables_except_alembic_version()

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="사용자 고유 식별자(UUID)",
        ),
        sa.Column("email", sa.String(length=255), nullable=False, comment="로그인 이메일"),
        sa.Column("nickname", sa.String(length=80), nullable=False, comment="서비스 표시 닉네임"),
        sa.Column(
            "auth_provider",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'LOCAL'"),
            comment="LOCAL / GOOGLE / KAKAO / NAVER",
        ),
        sa.Column("provider_id", sa.String(length=255), nullable=True, comment="OAuth 제공자 내부 사용자 ID"),
        sa.Column("profile_image_url", sa.String(length=500), nullable=True, comment="프로필 이미지 URL"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true"), comment="활성/휴면 상태"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), comment="생성 시각"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), comment="수정 시각"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        comment="사용자 기준 테이블",
    )
    op.create_index("idx_users_oauth", "users", ["auth_provider", "provider_id"], unique=False)

    op.create_table(
        "user_sync_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, comment="사용자 FK"),
        sa.Column("target_job", sa.String(length=100), nullable=True, comment="목표 직무"),
        sa.Column(
            "interest_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="관심 키워드 배열",
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), comment="갱신 시각"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        comment="사용자 명시적 관심사/목표 직무",
    )


def downgrade() -> None:
    op.drop_table("user_sync_profiles")
    op.drop_index("idx_users_oauth", table_name="users")
    op.drop_table("users")
