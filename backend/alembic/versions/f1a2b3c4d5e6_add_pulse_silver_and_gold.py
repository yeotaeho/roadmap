"""Pulse Silver(refined_pulse_metric_silver)·Gold(pulse_metrics_log) 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e2c5a7b9d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # refined_pulse_metric_silver — 섹터×일자 정규화 시계열 Silver (Pulse 입력)
    # ------------------------------------------------------------------
    op.create_table(
        "refined_pulse_metric_silver",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("sub_sector_id", sa.BigInteger(), nullable=True),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("raw_signal_value", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("normalized_score", sa.Integer(), nullable=True),
        sa.Column("momentum_pct", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("status_badge", sa.String(length=20), nullable=True),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("baseline_method", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["sector_slug"], ["sectors.slug"], name="fk_refined_pulse_silver_sector"
        ),
        sa.ForeignKeyConstraint(
            ["sub_sector_id"], ["sub_sectors.id"], name="fk_refined_pulse_silver_sub_sector"
        ),
        sa.CheckConstraint(
            "normalized_score BETWEEN 0 AND 100", name="ck_refined_pulse_silver_score"
        ),
        comment="Silver — 섹터×일자 정규화 Pulse 시계열 (Gold pulse_metrics_log 입력, 멱등)",
    )
    op.create_index(
        "ix_refined_pulse_silver_sector_date",
        "refined_pulse_metric_silver",
        ["sector_slug", sa.text("reference_date DESC")],
    )
    # 멱등 재처리용 자연키. sub_sector_id NULL 행도 유일성을 보장하려 COALESCE 식 인덱스 사용.
    op.create_index(
        "uq_refined_pulse_silver_natural",
        "refined_pulse_metric_silver",
        ["sector_slug", sa.text("COALESCE(sub_sector_id, -1)"), "reference_date", "baseline_method"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # pulse_metrics_log — Pulse 탭 서빙 Gold (Silver 사영)
    # ------------------------------------------------------------------
    op.create_table(
        "pulse_metrics_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("sub_sector_id", sa.BigInteger(), nullable=True),
        sa.Column("recorded_date", sa.Date(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("status_badge", sa.String(length=20), nullable=False),
        sa.Column("momentum_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["sector_slug"], ["sectors.slug"], name="fk_pulse_metrics_sector"
        ),
        sa.ForeignKeyConstraint(
            ["sub_sector_id"], ["sub_sectors.id"], name="fk_pulse_metrics_sub_sector"
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="ck_pulse_metrics_score"),
        comment="Gold — Pulse 탭 섹터별 일별 트렌드 점수 (멱등 재생성)",
    )
    op.create_index(
        "idx_pulse_metrics_date_sector",
        "pulse_metrics_log",
        ["recorded_date", "sector_slug"],
    )
    # 멱등 재생성용 자연키 (sub_sector_id NULL 안전).
    op.create_index(
        "uq_pulse_metrics_natural",
        "pulse_metrics_log",
        ["sector_slug", sa.text("COALESCE(sub_sector_id, -1)"), "recorded_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_pulse_metrics_natural", table_name="pulse_metrics_log")
    op.drop_index("idx_pulse_metrics_date_sector", table_name="pulse_metrics_log")
    op.drop_table("pulse_metrics_log")

    op.drop_index(
        "uq_refined_pulse_silver_natural", table_name="refined_pulse_metric_silver"
    )
    op.drop_index(
        "ix_refined_pulse_silver_sector_date", table_name="refined_pulse_metric_silver"
    )
    op.drop_table("refined_pulse_metric_silver")
