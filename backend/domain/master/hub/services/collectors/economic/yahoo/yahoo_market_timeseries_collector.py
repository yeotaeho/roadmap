"""Yahoo Finance 일별 OHLCV → `raw_market_timeseries` Bronze 수집.

`yahoo_finance_collector` 와 동일한 16개 티커(`VOLUME_SURGE_TARGETS`)에 대해
급증 여부와 무관하게 **모든 유효 거래일**의 OHLCV·추정 거래대금을 적재한다.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import date

from pandas import Timestamp

from domain.master.hub.services.collectors.economic.yahoo.yahoo_finance_collector import (
    VOLUME_SURGE_TARGETS,
    VolumeSurgeTarget,
    _INTER_TICKER_SLEEP_SEC,
    _drop_trailing_nan,
    _to_kst,
    _vwap_approx,
)
from domain.master.models.transfer.market_timeseries_dto import MarketTimeseriesDto

logger = logging.getLogger(__name__)

_DEFAULT_PERIOD = "1y"
_INCREMENTAL_PERIOD = "1mo"


def _trade_date_from_index(ts: Timestamp) -> date:
    return _to_kst(ts).date()


def _row_to_dto(target: VolumeSurgeTarget, row, trade_dt: date) -> MarketTimeseriesDto | None:
    try:
        close = float(row["Close"])
        volume = int(float(row["Volume"]))
    except (TypeError, ValueError, KeyError):
        return None

    if volume <= 0 or math.isnan(close) or close <= 0:
        return None

    def _f(col: str) -> float | None:
        if col not in row.index:
            return None
        try:
            v = float(row[col])
            if math.isnan(v):
                return None
            return v
        except (TypeError, ValueError):
            return None

    high = _f("High")
    low = _f("Low")
    open_p = _f("Open")
    h = high if high is not None else close
    l = low if low is not None else close
    vwap = _vwap_approx(h, l, close)
    turnover = int(round(volume * vwap))

    return MarketTimeseriesDto(
        ticker=target.ticker,
        trade_date=trade_dt,
        source_type=target.source_type,
        asset_name=target.name,
        theme=target.theme,
        currency=target.currency_code,
        open_price=open_p,
        high_price=high,
        low_price=low,
        close_price=close,
        volume=volume,
        turnover_amount=turnover,
        raw_metadata={
            "data_provider": "yfinance",
            "vwap_approx": round(vwap, 4),
            "turnover_calc": "volume * (high + low + close) / 3",
        },
    )


def _hist_to_dtos(target: VolumeSurgeTarget, hist) -> list[MarketTimeseriesDto]:
    hist = _drop_trailing_nan(hist)
    if hist is None or hist.empty:
        return []

    out: list[MarketTimeseriesDto] = []
    for i in range(len(hist)):
        row = hist.iloc[i]
        ts: Timestamp = hist.index[i]  # type: ignore[assignment]
        trade_dt = _trade_date_from_index(ts)
        dto = _row_to_dto(target, row, trade_dt)
        if dto is not None:
            out.append(dto)
    return out


class YahooMarketTimeseriesCollector:
    """16개 모니터링 티커의 일별 OHLCV 시계열 수집."""

    def __init__(
        self,
        targets: tuple[VolumeSurgeTarget, ...] = VOLUME_SURGE_TARGETS,
        *,
        inter_ticker_sleep_sec: float = _INTER_TICKER_SLEEP_SEC,
    ):
        self._targets = targets
        self._sleep_sec = inter_ticker_sleep_sec

    def collect_sync(
        self,
        *,
        period: str | None = None,
        incremental: bool = True,
    ) -> tuple[list[MarketTimeseriesDto], int]:
        """동기 수집 — yfinance history 전 거래일 파싱.

        Args:
            period: yfinance ``history(period=...)``. None이면 incremental 여부에 따라 기본값.
            incremental: True면 ``1mo``(일일 스케줄용), False면 ``1y``(초기 backfill).
        """
        import yfinance as yf

        if period:
            p = period
        elif incremental:
            p = _INCREMENTAL_PERIOD
        else:
            p = _DEFAULT_PERIOD

        out: list[MarketTimeseriesDto] = []
        failed = 0

        for i, target in enumerate(self._targets):
            if i > 0 and self._sleep_sec > 0:
                time.sleep(self._sleep_sec)

            try:
                hist = yf.Ticker(target.ticker).history(
                    period=p,
                    auto_adjust=False,
                )
            except Exception:
                logger.exception(
                    "Yahoo TS[%s] history 다운로드 실패", target.ticker
                )
                failed += 1
                continue

            try:
                rows = _hist_to_dtos(target, hist)
            except Exception:
                logger.exception(
                    "Yahoo TS[%s] OHLCV 파싱 실패", target.ticker
                )
                failed += 1
                continue

            out.extend(rows)
            logger.debug(
                "Yahoo TS[%s] %s rows period=%s",
                target.ticker,
                len(rows),
                p,
            )

        logger.info(
            "Yahoo market timeseries: %s rows, failed_tickers=%s period=%s incremental=%s",
            len(out),
            failed,
            p,
            incremental,
        )
        return out, failed

    async def collect(
        self,
        *,
        period: str | None = None,
        incremental: bool = True,
    ) -> tuple[list[MarketTimeseriesDto], int]:
        return await asyncio.to_thread(
            self.collect_sync,
            period=period,
            incremental=incremental,
        )
