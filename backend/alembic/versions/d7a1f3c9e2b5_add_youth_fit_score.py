"""refined_gap_insights 에 youth_fit_score 컬럼 추가(KIAT Gap 적합도 게이트)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7a1f3c9e2b5"
down_revision: Union[str, None] = "c5f9a3b7d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "refined_gap_insights",
        sa.Column("youth_fit_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("refined_gap_insights", "youth_fit_score")
