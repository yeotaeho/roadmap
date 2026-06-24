"""refined_text_sector_class(자유 텍스트 LLM 섹터 분류 Silver) 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b2d4f6a8c0e1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # refined_text_sector_class — raw 자유 텍스트의 LLM 섹터 분류 결과(Silver)
    # ------------------------------------------------------------------
    op.create_table(
        "refined_text_sector_class",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("raw_table_ref", sa.String(length=40), nullable=False),
        sa.Column("raw_id", sa.BigInteger(), nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["sector_slug"], ["sectors.slug"], name="fk_refined_text_sector_sector"
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence BETWEEN 0 AND 1)",
            name="ck_refined_text_sector_confidence",
        ),
        comment="Silver — raw 자유 텍스트 LLM 섹터 분류(economic_text·discourse 축 입력, 멱등)",
    )
    # 멱등 재처리용 자연키 (raw 행 × 프롬프트 버전).
    op.create_index(
        "uq_refined_text_sector_natural",
        "refined_text_sector_class",
        ["raw_table_ref", "raw_id", "prompt_version"],
        unique=True,
    )
    # 축 집계 조회 가속.
    op.create_index(
        "ix_refined_text_sector_lookup",
        "refined_text_sector_class",
        ["raw_table_ref", "sector_slug", "confidence"],
    )


def downgrade() -> None:
    op.drop_index("ix_refined_text_sector_lookup", table_name="refined_text_sector_class")
    op.drop_index("uq_refined_text_sector_natural", table_name="refined_text_sector_class")
    op.drop_table("refined_text_sector_class")
