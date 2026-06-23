"""시장 시계열 ORM과 DB 주석을 최신 상태로 동기화한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "c8d4e6f1a2b3"
down_revision: Union[str, None] = "b6c9d2e4f7a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "raw_market_timeseries",
        "trade_date",
        existing_type=sa.Date(),
        comment="거래일(시장 기준일)",
        existing_nullable=False,
    )
    op.alter_column(
        "raw_market_timeseries",
        "source_type",
        existing_type=sa.String(length=50),
        comment="YAHOO_ETF_AI, YAHOO_STOCK_KR_* 등",
        existing_nullable=False,
    )
    op.alter_column(
        "raw_market_timeseries",
        "asset_name",
        existing_type=sa.String(length=255),
        comment="표시명",
        existing_nullable=False,
    )
    op.alter_column(
        "raw_market_timeseries",
        "theme",
        existing_type=sa.String(length=100),
        comment="테마/섹터 라벨",
        existing_nullable=True,
    )
    op.alter_column(
        "raw_market_timeseries",
        "currency",
        existing_type=sa.String(length=10),
        comment="가격·거래대금 통화",
        existing_nullable=False,
        existing_server_default=sa.text("'KRW'::character varying"),
    )
    op.alter_column(
        "raw_market_timeseries",
        "volume",
        existing_type=sa.BigInteger(),
        comment="거래량(주)",
        existing_nullable=False,
    )
    op.alter_column(
        "raw_market_timeseries",
        "turnover_amount",
        existing_type=sa.BigInteger(),
        comment="추정 거래대금(volume×VWAP근사)",
        existing_nullable=True,
    )
    op.alter_column(
        "raw_market_timeseries",
        "raw_metadata",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        comment="vwap_approx, data_provider 등",
        existing_nullable=True,
    )
    op.alter_column(
        "raw_market_timeseries",
        "collected_at",
        existing_type=sa.DateTime(timezone=True),
        comment="수집·갱신 시각",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.create_table_comment(
        "raw_market_timeseries",
        "Bronze — Yahoo 등 일별 OHLCV·거래대금 시계열",
        existing_comment="Bronze — 일별 OHLCV·거래대금 시계열",
    )


def downgrade() -> None:
    op.create_table_comment(
        "raw_market_timeseries",
        "Bronze — 일별 OHLCV·거래대금 시계열",
        existing_comment="Bronze — Yahoo 등 일별 OHLCV·거래대금 시계열",
    )
    for column, existing_type, old_comment, nullable in (
        ("trade_date", sa.Date(), "거래일", False),
        ("source_type", sa.String(length=50), "YAHOO_ETF_AI 등", False),
        ("asset_name", sa.String(length=255), None, False),
        ("theme", sa.String(length=100), None, True),
        ("currency", sa.String(length=10), None, False),
        ("volume", sa.BigInteger(), None, False),
        ("turnover_amount", sa.BigInteger(), None, True),
        ("raw_metadata", postgresql.JSONB(astext_type=sa.Text()), None, True),
        ("collected_at", sa.DateTime(timezone=True), None, False),
    ):
        op.alter_column(
            "raw_market_timeseries",
            column,
            existing_type=existing_type,
            comment=old_comment,
            existing_nullable=nullable,
        )
