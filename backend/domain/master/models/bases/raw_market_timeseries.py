"""Bronze: 상장·ETF 일별 OHLCV 시계열 (`raw_market_timeseries`).

`raw_economic_data` 는 이벤트·신호(뉴스, 거래량 급증) 단위이고,
본 테이블은 티커×거래일 단위의 **연속 시계열** 원본을 보관한다.
Silver 에서 급증·Z-score·섹터 모멘텀 등을 산출할 때 사용한다.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RawMarketTimeseries(Base):
    __tablename__ = "raw_market_timeseries"
    __table_args__ = (
        UniqueConstraint("ticker", "trade_date", name="uq_raw_market_timeseries_ticker_date"),
        {"comment": "Bronze — Yahoo 등 일별 OHLCV·거래대금 시계열"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    ticker: Mapped[str] = mapped_column(String(32), nullable=False, comment="yfinance 심볼")
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, comment="거래일(시장 기준일)")

    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="YAHOO_ETF_AI, YAHOO_STOCK_KR_* 등"
    )
    asset_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="표시명")
    theme: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="테마/섹터 라벨")
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="KRW", comment="가격·거래대금 통화"
    )

    open_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    high_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    low_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    close_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="거래량(주)")
    turnover_amount: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="추정 거래대금(volume×VWAP근사)"
    )

    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="vwap_approx, data_provider 등")

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="수집·갱신 시각",
    )
