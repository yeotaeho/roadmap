"""user_profiles·user_preferences 생성 + user_personas 스펙 4컬럼 추가."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a3f7c1e9d2b4"
down_revision: Union[str, None] = "c8f1a2d3e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 기본정보(데모그래픽) — auth 소유, 전부 nullable ──
    op.create_table(
        "user_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("birth_year", sa.SmallInteger(), nullable=True),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("current_status", sa.String(length=20), nullable=True),
        sa.Column("education_level", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=20), server_default="user_form", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_profile_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
        comment="사용자 기본정보(데모그래픽) - 선택 입력, 임베딩 직렬화 제외",
    )

    # ── 성향·선호 — user_intelligence 소유, 전부 nullable ──
    op.create_table(
        "user_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_style", sa.String(length=20), nullable=True),
        sa.Column("company_size_pref", sa.String(length=20), nullable=True),
        sa.Column("work_type_pref", sa.String(length=20), nullable=True),
        sa.Column("work_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.String(length=20), server_default="user_form", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_preference_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
        comment="사용자 성향·선호 - 작업성향·기업규모·근무형태·일의가치(선택 입력)",
    )

    # ── persona 스펙 심화 4컬럼(nullable) ──
    op.add_column("user_personas", sa.Column("certifications", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("user_personas", sa.Column("languages", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("user_personas", sa.Column("links", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("user_personas", sa.Column("projects", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("user_personas", "projects")
    op.drop_column("user_personas", "links")
    op.drop_column("user_personas", "languages")
    op.drop_column("user_personas", "certifications")
    op.drop_table("user_preferences")
    op.drop_table("user_profiles")
