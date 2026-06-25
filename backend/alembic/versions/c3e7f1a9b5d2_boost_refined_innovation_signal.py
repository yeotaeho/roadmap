"""refined_innovation_signal에 LLM 추적 컬럼·멱등 자연키를 보강한다(엔티티·키워드 추출 적재용)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3e7f1a9b5d2"
down_revision: Union[str, None] = "b2d4f6a8c0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "refined_innovation_signal", sa.Column("model_name", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "refined_innovation_signal", sa.Column("prompt_version", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "refined_innovation_signal", sa.Column("input_hash", sa.String(length=64), nullable=True)
    )
    # 멱등 자연키 — 같은 (섹터·신호종류·토픽·기준기간)은 한 신호로 합류(N:M source 누적).
    op.create_index(
        "uq_refined_innov_natural",
        "refined_innovation_signal",
        ["sector_slug", "data_role", "signal_topic", "reference_period_start", "reference_period_end"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_refined_innov_natural", table_name="refined_innovation_signal")
    op.drop_column("refined_innovation_signal", "input_hash")
    op.drop_column("refined_innovation_signal", "prompt_version")
    op.drop_column("refined_innovation_signal", "model_name")
