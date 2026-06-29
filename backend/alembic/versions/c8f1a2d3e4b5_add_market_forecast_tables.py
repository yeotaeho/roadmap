"""시장 전망 수직 — refined_market_forecast_silver·market_forecast_log 테이블 생성(TimesFM 예측)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c8f1a2d3e4b5"
down_revision: Union[str, None] = "d1a2b3c4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refined_market_forecast_silver",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("predicted_return_pct", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("forecast_score", sa.Integer(), nullable=True),
        sa.Column("direction_badge", sa.String(length=20), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("ticker_count", sa.Integer(), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("forecast_score BETWEEN 0 AND 100", name="ck_market_forecast_silver_score"),
        sa.ForeignKeyConstraint(["sector_slug"], ["sectors.slug"], name="fk_market_forecast_silver_sector"),
        sa.PrimaryKeyConstraint("id"),
        comment="Silver — 섹터×기준일 시장 전망 시계열 (Gold market_forecast_log 입력, 멱등)",
    )
    op.create_index(
        "ix_market_forecast_silver_sector_date",
        "refined_market_forecast_silver",
        ["sector_slug", sa.text("reference_date DESC")],
    )
    op.create_index(
        "uq_market_forecast_silver_natural",
        "refined_market_forecast_silver",
        ["sector_slug", "reference_date", "horizon_days"],
        unique=True,
    )

    op.create_table(
        "market_forecast_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("direction_badge", sa.String(length=20), nullable=False),
        sa.Column("predicted_return_pct", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="ck_market_forecast_log_score"),
        sa.ForeignKeyConstraint(["sector_slug"], ["sectors.slug"], name="fk_market_forecast_log_sector"),
        sa.PrimaryKeyConstraint("id"),
        comment="Gold — 시장 전망 섹터별 기준일 예측 점수 (멱등 재생성)",
    )
    op.create_index(
        "idx_market_forecast_date_sector",
        "market_forecast_log",
        ["forecast_date", "sector_slug"],
    )
    op.create_index(
        "uq_market_forecast_log_natural",
        "market_forecast_log",
        ["sector_slug", "forecast_date", "horizon_days"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("market_forecast_log")
    op.drop_table("refined_market_forecast_silver")
