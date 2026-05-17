"""Bronze: raw_market_timeseries (일별 OHLCV 시계열)."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a3f8c2d1e9b4"
down_revision: Union[str, None] = "e1f7c8a3b9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_market_timeseries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False, comment="yfinance 심볼"),
        sa.Column("trade_date", sa.Date(), nullable=False, comment="거래일"),
        sa.Column(
            "source_type",
            sa.String(length=50),
            nullable=False,
            comment="YAHOO_ETF_AI 등",
        ),
        sa.Column("asset_name", sa.String(length=255), nullable=False),
        sa.Column("theme", sa.String(length=100), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=10),
            server_default="KRW",
            nullable=False,
        ),
        sa.Column("open_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("high_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("low_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("close_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("turnover_amount", sa.BigInteger(), nullable=True),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker",
            "trade_date",
            name="uq_raw_market_timeseries_ticker_date",
        ),
        comment="Bronze — 일별 OHLCV·거래대금 시계열",
    )
    op.create_index(
        "ix_raw_market_ts_ticker_date",
        "raw_market_timeseries",
        ["ticker", "trade_date"],
        unique=False,
    )
    op.create_index(
        "ix_raw_market_ts_trade_date",
        "raw_market_timeseries",
        ["trade_date"],
        unique=False,
    )
    op.create_index(
        "ix_raw_market_ts_source_type",
        "raw_market_timeseries",
        ["source_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_raw_market_ts_source_type", table_name="raw_market_timeseries")
    op.drop_index("ix_raw_market_ts_trade_date", table_name="raw_market_timeseries")
    op.drop_index("ix_raw_market_ts_ticker_date", table_name="raw_market_timeseries")
    op.drop_table("raw_market_timeseries")
