"""refined_text_sector_class에 감성 컬럼(sentiment·sentiment_score)을 추가한다(Pulse 점수 방향성 가산 이동 입력)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a9d2f7c4e1b8"
down_revision: Union[str, None] = "8ada7f5586d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "refined_text_sector_class",
        sa.Column(
            "sentiment",
            sa.String(length=10),
            nullable=True,
            comment="LLM 감성 판정 '긍정'/'중립'/'부정'. 무판정이면 NULL",
        ),
    )
    op.add_column(
        "refined_text_sector_class",
        sa.Column(
            "sentiment_score",
            sa.Numeric(precision=3, scale=2),
            nullable=True,
            comment="감성 점수 -1.0(부정)~1.0(긍정). Pulse 점수 가산 이동 입력",
        ),
    )
    op.create_check_constraint(
        "ck_refined_text_sector_sentiment_enum",
        "refined_text_sector_class",
        "sentiment IS NULL OR sentiment IN ('긍정', '중립', '부정')",
    )
    op.create_check_constraint(
        "ck_refined_text_sector_sentiment_score",
        "refined_text_sector_class",
        "sentiment_score IS NULL OR (sentiment_score BETWEEN -1 AND 1)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_refined_text_sector_sentiment_score", "refined_text_sector_class", type_="check"
    )
    op.drop_constraint(
        "ck_refined_text_sector_sentiment_enum", "refined_text_sector_class", type_="check"
    )
    op.drop_column("refined_text_sector_class", "sentiment_score")
    op.drop_column("refined_text_sector_class", "sentiment")
