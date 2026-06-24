"""pulse momentum_pct 정밀도 확장 — 실데이터 모멘텀이 999%를 초과해 오버플로하던 문제 수정."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 모멘텀(%)은 작은 기준선 대비 급등 시 수천 %까지 가능 → NUMERIC(8,2)로 확장.
    op.alter_column(
        "pulse_metrics_log",
        "momentum_pct",
        existing_type=sa.Numeric(precision=5, scale=2),
        type_=sa.Numeric(precision=8, scale=2),
        existing_nullable=True,
    )
    op.alter_column(
        "refined_pulse_metric_silver",
        "momentum_pct",
        existing_type=sa.Numeric(precision=6, scale=2),
        type_=sa.Numeric(precision=8, scale=2),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "refined_pulse_metric_silver",
        "momentum_pct",
        existing_type=sa.Numeric(precision=8, scale=2),
        type_=sa.Numeric(precision=6, scale=2),
        existing_nullable=True,
    )
    op.alter_column(
        "pulse_metrics_log",
        "momentum_pct",
        existing_type=sa.Numeric(precision=8, scale=2),
        type_=sa.Numeric(precision=5, scale=2),
        existing_nullable=True,
    )
