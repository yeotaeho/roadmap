"""Yahoo Finance 거시 지표(Macro) 가격 변동 기반 경제 Bronze 수집.

설계 메모 (2026-05-12 Option B 신규):
  - 가설: 환율 / 국채 금리 / 원자재는 **거래량 개념이 없거나 무의미**(USDKRW=X 등 Volume=0)
          → "가격 변동률의 통계적 이상치" 가 자본 흐름 변화의 신호.
  - 알고리즘: **Z-score 기반 가격 변동 급증 (Price Surge)**
      r_t = (close_t / close_{t-1}) - 1                 ← 일간 수익률 (소수)
      σ_20 = std(r over previous 20 trading days)       ← 마지막 행 제외 20일 표준편차
      Z = |r_t| / σ_20
      Z >= threshold → Bronze 적재

자산 그룹:
  - FX (환율)        : 외국인 자본의 한국 시장 유출입 직접 신호
  - RATE (국채 금리) : 글로벌 자본 비용 / 무위험 수익률 변화
  - COMMODITY (원자재): 안전자산 vs 위험자산 자본 이동
  - CRYPTO (가상자산): 위험자산 극단 (변동성 큼 → 임계값 ↑)

운영 메모:
  - `investment_amount` = `None`: 가격 변동은 흐름량을 직접 측정할 수 없음
                                  (`raw_metadata` 에 수익률/Z-score 등 정량 정보 보존)
  - NaN 후행 행 제거: yfinance 가 미정산 거래일을 NaN 으로 줄 수 있음
  - 티커 간 0.5s sleep: IP 차단 방어
  - `source_url` = `https://finance.yahoo.com/quote/<ticker>/history?period1=YYYY-MM-DD`
    → (티커, 거래일) 단위 유일성으로 중복 적재 방지
  - 통화: 자산별 currency_code (KRW / USD / PCT)
      * PCT 는 금리(%, 단위 없음)용 표시
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import yfinance as yf
from pandas import DataFrame, Timestamp

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)


_KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class MacroTarget:
    """거시 지표 모니터링 대상 자산."""

    ticker: str
    name: str
    category: str  # "FX" / "RATE" / "COMMODITY" / "CRYPTO"
    source_type: str  # 예: "YAHOO_FX_USDKRW", "YAHOO_RATE_US10Y"
    threshold: float  # Z-score 임계값 (정규분포 가정 시 2.0 ≒ 상위 5%)
    currency_code: str  # "KRW" / "USD" / "PCT"
    unit_label: str  # 표시용 단위 (예: "원", "달러", "%", "BTC")


# =============================================================================
# 거시 지표 대상 (8종) — 카테고리별 임계값 차등 적용
# =============================================================================
MACRO_TARGETS: tuple[MacroTarget, ...] = (
    # --- FX (환율) — 외국인 자본의 국가 간 이동 ---
    MacroTarget(
        ticker="USDKRW=X",
        name="원/달러 환율",
        category="FX",
        source_type="YAHOO_FX_USDKRW",
        threshold=2.0,
        currency_code="KRW",
        unit_label="원/USD",
    ),
    MacroTarget(
        ticker="EURKRW=X",
        name="원/유로 환율",
        category="FX",
        source_type="YAHOO_FX_EURKRW",
        threshold=2.0,
        currency_code="KRW",
        unit_label="원/EUR",
    ),
    MacroTarget(
        ticker="JPYKRW=X",
        name="원/엔 환율",
        category="FX",
        source_type="YAHOO_FX_JPYKRW",
        threshold=2.0,
        currency_code="KRW",
        unit_label="원/JPY",
    ),
    # --- RATE (국채 금리) — 글로벌 자본 비용 / 무위험 수익률 ---
    MacroTarget(
        ticker="^TNX",
        name="미 10년물 국채금리",
        category="RATE",
        source_type="YAHOO_RATE_US10Y",
        threshold=2.0,
        currency_code="PCT",
        unit_label="%",
    ),
    MacroTarget(
        ticker="^IRX",
        name="미 13주 단기 국채금리",
        category="RATE",
        source_type="YAHOO_RATE_US3M",
        threshold=2.0,
        currency_code="PCT",
        unit_label="%",
    ),
    # --- COMMODITY (원자재) — 안전자산/산업 비용 ---
    MacroTarget(
        ticker="GC=F",
        name="국제 금 선물",
        category="COMMODITY",
        source_type="YAHOO_COMMODITY_GOLD",
        threshold=2.0,
        currency_code="USD",
        unit_label="USD/oz",
    ),
    MacroTarget(
        ticker="CL=F",
        name="WTI 원유 선물",
        category="COMMODITY",
        source_type="YAHOO_COMMODITY_OIL",
        threshold=2.0,
        currency_code="USD",
        unit_label="USD/bbl",
    ),
    # --- CRYPTO (가상자산) — 위험자산 극단 (변동성 큼 → Z 임계값 ↑) ---
    MacroTarget(
        ticker="BTC-USD",
        name="비트코인",
        category="CRYPTO",
        source_type="YAHOO_COMMODITY_BTC",
        threshold=2.5,
        currency_code="USD",
        unit_label="USD/BTC",
    ),
)

# Z-score 계산 윈도우 (거래일).
_Z_WINDOW = 20

# `period` 인자: 일간 수익률 계산 + 20일 표준편차 분량 확보.
_HISTORY_PERIOD = "1y"

# IP 차단 방어용 티커 간 sleep.
_INTER_TICKER_SLEEP_SEC = 0.5


def _to_local_dt(ts: Timestamp) -> datetime:
    """`pandas.Timestamp` → tz-aware datetime (없으면 KST 부여)."""
    py_dt = ts.to_pydatetime()
    if py_dt.tzinfo is None:
        return py_dt.replace(tzinfo=_KST)
    return py_dt


def _drop_trailing_nan_close(hist: DataFrame) -> DataFrame:
    """`Close` 가 NaN 인 후행 행을 잘라낸다. Macro 지표는 Volume=0 이 정상이므로 Close 만 확인."""
    if hist is None or hist.empty or "Close" not in hist.columns:
        return hist

    last_valid_idx = -1
    for i in range(len(hist) - 1, -1, -1):
        val = hist.iloc[i]["Close"]
        if val is None or (isinstance(val, float) and math.isnan(val)):
            continue
        last_valid_idx = i
        break

    if last_valid_idx < 0:
        return hist.iloc[0:0]
    return hist.iloc[: last_valid_idx + 1]


def _compute_zscore_dto(
    target: MacroTarget,
    hist: DataFrame,
) -> EconomicCollectDto | None:
    """Z-score 가 임계값 초과 시 Bronze DTO 1건 반환, 미달이면 None."""
    hist = _drop_trailing_nan_close(hist)

    # 일간 수익률 계산을 위해 최소 (윈도우 + 2) 행 필요 (이전 거래일 close 필요)
    if hist is None or hist.empty or len(hist) < _Z_WINDOW + 2:
        logger.warning(
            "Yahoo Macro[%s] 데이터 부족 — rows=%s (필요 >= %s)",
            target.ticker,
            0 if hist is None else len(hist),
            _Z_WINDOW + 2,
        )
        return None

    closes = hist["Close"].astype(float)
    returns = closes.pct_change().dropna()
    if returns.empty:
        return None

    last_return = float(returns.iloc[-1])
    if math.isnan(last_return):
        return None

    prev_window = returns.iloc[-(_Z_WINDOW + 1):-1]
    std_20 = float(prev_window.std())
    if std_20 <= 0 or math.isnan(std_20):
        logger.debug("Yahoo Macro[%s] σ_20=%s 비유효 — 스킵", target.ticker, std_20)
        return None

    z_score = abs(last_return) / std_20
    if z_score < target.threshold:
        logger.debug(
            "Yahoo Macro[%s] Z=%.2f < %.2f — 임계값 미달",
            target.ticker,
            z_score,
            target.threshold,
        )
        return None

    last_close = float(closes.iloc[-1])
    prev_close = float(closes.iloc[-2])
    last_ts: Timestamp = hist.index[-1]  # type: ignore[assignment]
    trade_date_local = _to_local_dt(last_ts)
    date_str = trade_date_local.strftime("%Y-%m-%d")

    direction = "급등" if last_return > 0 else "급락"
    pct_str = f"{last_return * 100:+.2f}%"
    raw_title = (
        f"{target.name}({target.ticker}) {direction} {pct_str} "
        f"(Z={z_score:.2f}, {date_str}, 종가 {last_close:,.4g}{target.unit_label})"
    )

    source_url = (
        f"https://finance.yahoo.com/quote/{target.ticker}/history?period1={date_str}"
    )

    raw_metadata: dict[str, object] = {
        "ticker": target.ticker,
        "asset_name": target.name,
        "category": target.category,
        "unit": target.unit_label,
        "trade_date": date_str,
        "close": last_close,
        "prev_close": prev_close,
        "daily_return": round(last_return, 6),
        "daily_return_pct": round(last_return * 100, 4),
        "std_20d": round(std_20, 6),
        "z_score": round(z_score, 3),
        "threshold": target.threshold,
        "direction": "up" if last_return > 0 else "down",
        "calculation_method": "z = |daily_return| / std_20d(prev 20 trading days)",
    }

    return EconomicCollectDto(
        source_type=target.source_type[:50],
        source_url=source_url,
        raw_title=raw_title[:500],
        investor_name=None,
        target_company_or_fund=target.name[:255],
        investment_amount=None,  # Macro 가격 변동은 흐름량 직접 측정 불가
        currency=target.currency_code[:10],
        raw_metadata=raw_metadata,
        published_at=trade_date_local,
    )


class YahooMacroCollector:
    """거시 지표 가격 변동(Price Surge) Collector — FX / Rate / Commodity / Crypto.

    동작:
      1) `MACRO_TARGETS` 각 자산의 60일 시세 다운로드
      2) NaN Close 후행 행 제거
      3) 일간 수익률 시계열 산출 → 이전 20일 표준편차(σ_20)
      4) `Z = |last_return| / σ_20` 가 자산별 임계값 초과 시 Bronze DTO 1건 생성

    Bronze Layer 정합성:
      - `investment_amount = None`: 가격 변동은 흐름량을 정의할 수 없음
      - 모든 정량 데이터는 `raw_metadata` 에 보존 (Silver 단계에서 활용)
    """

    def __init__(
        self,
        targets: tuple[MacroTarget, ...] = MACRO_TARGETS,
        *,
        inter_ticker_sleep_sec: float = _INTER_TICKER_SLEEP_SEC,
    ):
        self._targets = targets
        self._sleep_sec = inter_ticker_sleep_sec

    def collect_sync(self) -> tuple[list[EconomicCollectDto], int]:
        out: list[EconomicCollectDto] = []
        skipped = 0

        for i, target in enumerate(self._targets):
            if i > 0 and self._sleep_sec > 0:
                time.sleep(self._sleep_sec)

            try:
                hist = yf.Ticker(target.ticker).history(
                    period=_HISTORY_PERIOD,
                    auto_adjust=False,
                )
            except Exception:
                logger.exception(
                    "Yahoo Macro[%s] history 다운로드 실패 — 다음 티커로 진행",
                    target.ticker,
                )
                skipped += 1
                continue

            try:
                dto = _compute_zscore_dto(target, hist)
            except Exception:
                logger.exception(
                    "Yahoo Macro[%s] Z-score 계산 중 예외 — 다음 티커로 진행",
                    target.ticker,
                )
                skipped += 1
                continue

            if dto is None:
                skipped += 1
                continue

            out.append(dto)

        logger.info(
            "Yahoo Macro 수집 완료: %s개 신호 / %s개 스킵 (총 %s 자산)",
            len(out),
            skipped,
            len(self._targets),
        )
        return out, skipped

    async def collect(self) -> tuple[list[EconomicCollectDto], int]:
        return await asyncio.to_thread(self.collect_sync)
