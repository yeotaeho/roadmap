"""economic_briefings(Gold) 3줄 경제 브리핑 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a7d3f1b9c2e4"
down_revision: Union[str, None] = "f8c2e6a0d3b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Gold — Pulse 3줄 경제 브리핑 (일자×줄번호 멱등) ──
    op.create_table(
        "economic_briefings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("published_date", sa.Date(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.String(length=255), nullable=False),
        sa.Column(
            "trend_icon",
            sa.String(length=20),
            nullable=False,
            comment="UP_RIGHT / DOWN_RIGHT / WAVE",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("line_number IN (1, 2, 3)", name="ck_briefing_line_number"),
        comment="Gold — Pulse 3줄 경제 브리핑 (일자×줄번호 멱등)",
    )
    op.create_index(
        "uq_economic_briefings_natural",
        "economic_briefings",
        ["published_date", "line_number"],
        unique=True,
    )
    op.create_index(
        "idx_economic_briefings_date",
        "economic_briefings",
        ["published_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_economic_briefings_date", table_name="economic_briefings")
    op.drop_index("uq_economic_briefings_natural", table_name="economic_briefings")
    op.drop_table("economic_briefings")
