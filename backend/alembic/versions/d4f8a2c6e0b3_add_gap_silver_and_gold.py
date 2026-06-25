"""Gap Silver(refined_gap_insights)·Gold(gap_issues·issue_evidences) 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "d4f8a2c6e0b3"
down_revision: Union[str, None] = "c3e7f1a9b5d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Silver — discourse 본문에서 추출한 미해결 문제·청년 기회 ──
    op.create_table(
        "refined_gap_insights",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("data_role", sa.String(length=50), nullable=False),
        sa.Column("extracted_problem", sa.Text(), nullable=True),
        sa.Column("extracted_opportunity", sa.Text(), nullable=True),
        sa.Column("detail_summary", sa.Text(), nullable=True),
        sa.Column("stakeholders", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("next_actions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(["sector_slug"], ["sectors.slug"], name="fk_refined_gap_sector"),
        comment="Silver — discourse 추출 미해결 문제·기회 (extracted_problem NULL = 무귀속 처리됨)",
    )
    op.create_index(
        "uq_refined_gap_natural",
        "refined_gap_insights",
        ["raw_table_ref", "raw_id", "prompt_version"],
        unique=True,
    )
    op.create_index("ix_refined_gap_sector", "refined_gap_insights", ["sector_slug"])

    # ── Gold — Gap 탭 카드(문제↔기회) ──
    op.create_table(
        "gap_issues",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("problem_summary", sa.String(length=255), nullable=False),
        sa.Column("chance_summary", sa.String(length=255), nullable=False),
        sa.Column("detail_summary", sa.Text(), nullable=True),
        sa.Column("stakeholders", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("next_actions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("published_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["sector_slug"], ["sectors.slug"], name="fk_gap_issues_sector"),
        comment="Gold — Gap 탭 카드 (세상의 문제 ↔ 청년의 기회, 멱등 재생성)",
    )
    op.create_index("ix_gap_issues_sector", "gap_issues", ["sector_slug"])

    # ── Gold — 이슈 근거(원천 링크) ──
    op.create_table(
        "issue_evidences",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("issue_id", sa.BigInteger(), nullable=False),
        sa.Column("evidence_type", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("raw_table_ref", sa.String(length=50), nullable=True),
        sa.Column("raw_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["issue_id"], ["gap_issues.id"], name="fk_issue_evidences_issue", ondelete="CASCADE"
        ),
        comment="Gold — Gap 이슈 근거(원천 기사/리포트 링크)",
    )
    op.create_index("ix_issue_evidences_issue", "issue_evidences", ["issue_id"])


def downgrade() -> None:
    op.drop_index("ix_issue_evidences_issue", table_name="issue_evidences")
    op.drop_table("issue_evidences")
    op.drop_index("ix_gap_issues_sector", table_name="gap_issues")
    op.drop_table("gap_issues")
    op.drop_index("ix_refined_gap_sector", table_name="refined_gap_insights")
    op.drop_index("uq_refined_gap_natural", table_name="refined_gap_insights")
    op.drop_table("refined_gap_insights")
