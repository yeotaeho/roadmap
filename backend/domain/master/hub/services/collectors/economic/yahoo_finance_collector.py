"""Yahoo Finance 거래량 급증(Volume Surge) 기반 경제 Bronze 수집.

설계 메모 (2026-05-12 Option B 확장 — 거래량 시계열 적용 자산을 11→16종으로 확장):
  - 가설      : "가격 상승"은 후행이지만, **"거래량 급증"은 선행 자본 유입 신호**다.
  - 데이터원  : `yfinance` 라이브러리 (Yahoo Finance 비공식 클라이언트)
  - 대상 자산 그룹 (3종):
      * 한국 테마 ETF      (`.KS`)           — 기존 5종 유지
      * 한국 대형주        (`.KS`)           — **신규 5종**: 삼성전자/SK하이닉스/LG에너지솔루션/삼성바이오/NAVER
      * 글로벌 ETF         (NYSE/Nasdaq)     — **신규 6종**: SPY/QQQ/SMH/ARKK/LIT/XLE
        → 한국 시장 대비 6~12시간 선행하므로 **선행 지표** 역할

Option B 핵심 차별점 (이번 확장에 반영):
  - **NaN 마지막행 안전처리**: yfinance 가 한국 시장 마감 전 마지막 행을 NaN 으로 줄 수 있음
    → 종가/거래량이 NaN 인 후행 행을 모두 제거하고 가장 최근 유효 거래일을 사용
  - **티커 간 0.5s sleep**: IP 차단 방어 (티커 수가 5→16 으로 늘면서 호출 빈도 증가)
  - **타임존**: 글로벌 ETF 는 미 동부시간(ET) → tz-aware 그대로 보존
  - **source_type 네임스페이스 분리**:
      * `YAHOO_ETF_*`      — 한국 테마 ETF (기존)
      * `YAHOO_STOCK_KR_*` — 한국 대형주 (신규)
      * `YAHOO_GLOBAL_*`   — 글로벌 ETF (신규)

운영 메모:
  - 데이터 신뢰: `history(period="1y")` 로 20일 이동평균 + 장기 시계열 확보
  - 통화      : `currency_code` 필드로 자산별 정확한 통화 기록 (KRW / USD)
  - 중복      : `source_url` 은 `(ticker, date)` 합성 → 동일 거래일 중복 적재 방지
  - 실패 격리 : 일부 티커 다운로드 실패는 logger 로 흡수, 다른 티커는 정상 진행
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

# 거래일 NaN 후행 행 제거 시 필수 컬럼.
_REQUIRED_COLS: tuple[str, ...] = ("Close", "Volume")


@dataclass(frozen=True)
class VolumeSurgeTarget:
    """거래량 급증 모니터링 대상 자산 (ETF / 개별주 공통)."""

    ticker: str
    name: str
    theme: str
    source_type: str
    threshold: float  # 20일 평균 거래량 대비 N배
    currency_code: str  # "KRW" or "USD"


# =============================================================================
# 그룹 1: 한국 테마 ETF (기존 5종, 변경 없음)
# =============================================================================
_KOREAN_ETF_TARGETS: tuple[VolumeSurgeTarget, ...] = (
    VolumeSurgeTarget(
        ticker="091220.KS",
        name="TIGER 글로벌AI액티브",
        theme="AI/반도체",
        source_type="YAHOO_ETF_AI",
        threshold=2.0,
        currency_code="KRW",
    ),
    VolumeSurgeTarget(
        ticker="441680.KS",
        name="KODEX 2차전지산업",
        theme="2차전지/배터리",
        source_type="YAHOO_ETF_BATTERY",
        threshold=2.0,
        currency_code="KRW",
    ),
    VolumeSurgeTarget(
        ticker="244620.KS",
        name="KODEX 바이오",
        theme="한국 바이오/제약",
        source_type="YAHOO_ETF_BIO",
        threshold=2.5,
        currency_code="KRW",
    ),
    VolumeSurgeTarget(
        ticker="261140.KS",
        name="KODEX K-신재생에너지액티브",
        theme="재생에너지/탄소중립",
        source_type="YAHOO_ETF_RENEWABLE",
        threshold=2.5,
        currency_code="KRW",
    ),
    VolumeSurgeTarget(
        ticker="332620.KS",
        name="TIGER K-푸드",
        theme="K-푸드/농식품",
        source_type="YAHOO_ETF_KFOOD",
        threshold=2.2,
        currency_code="KRW",
    ),
)

# =============================================================================
# 그룹 2: 한국 대형주 (신규 5종)
# 임계값은 평소 거래량이 풍부한 대형주일수록 낮게 (1.5배도 큰 신호).
# =============================================================================
_KOREAN_STOCK_TARGETS: tuple[VolumeSurgeTarget, ...] = (
    VolumeSurgeTarget(
        ticker="005930.KS",
        name="삼성전자",
        theme="반도체/IT 대표주",
        source_type="YAHOO_STOCK_KR_SAMSUNG",
        threshold=1.5,
        currency_code="KRW",
    ),
    VolumeSurgeTarget(
        ticker="000660.KS",
        name="SK하이닉스",
        theme="AI/반도체 메모리",
        source_type="YAHOO_STOCK_KR_HYNIX",
        threshold=1.5,
        currency_code="KRW",
    ),
    VolumeSurgeTarget(
        ticker="373220.KS",
        name="LG에너지솔루션",
        theme="2차전지 셀 1위",
        source_type="YAHOO_STOCK_KR_LGES",
        threshold=1.8,
        currency_code="KRW",
    ),
    VolumeSurgeTarget(
        ticker="207940.KS",
        name="삼성바이오로직스",
        theme="바이오 CDMO 대표주",
        source_type="YAHOO_STOCK_KR_SBIO",
        threshold=2.0,
        currency_code="KRW",
    ),
    VolumeSurgeTarget(
        ticker="035420.KS",
        name="NAVER",
        theme="인터넷/AI 플랫폼",
        source_type="YAHOO_STOCK_KR_NAVER",
        threshold=2.0,
        currency_code="KRW",
    ),
)

# =============================================================================
# 그룹 3: 글로벌 ETF (신규 6종) — 한국 시장 선행 지표
# 미국 시장이 6~12시간 먼저 마감되므로 신호가 한국 시장보다 앞선다.
# =============================================================================
_GLOBAL_ETF_TARGETS: tuple[VolumeSurgeTarget, ...] = (
    VolumeSurgeTarget(
        ticker="SPY",
        name="SPDR S&P 500 ETF",
        theme="미국 시장 대표 (S&P500)",
        source_type="YAHOO_GLOBAL_SPY",
        threshold=1.5,
        currency_code="USD",
    ),
    VolumeSurgeTarget(
        ticker="QQQ",
        name="Invesco QQQ Trust",
        theme="나스닥100 (테크/AI)",
        source_type="YAHOO_GLOBAL_QQQ",
        threshold=1.5,
        currency_code="USD",
    ),
    VolumeSurgeTarget(
        ticker="SMH",
        name="VanEck Semiconductor ETF",
        theme="반도체 — 한국 AI ETF 직접 선행",
        source_type="YAHOO_GLOBAL_SMH",
        threshold=2.0,
        currency_code="USD",
    ),
    VolumeSurgeTarget(
        ticker="ARKK",
        name="ARK Innovation ETF",
        theme="혁신기술 — 위험자산 선호도",
        source_type="YAHOO_GLOBAL_ARKK",
        threshold=2.0,
        currency_code="USD",
    ),
    VolumeSurgeTarget(
        ticker="LIT",
        name="Global X Lithium & Battery Tech ETF",
        theme="리튬/배터리 — 한국 2차전지 선행",
        source_type="YAHOO_GLOBAL_LIT",
        threshold=2.0,
        currency_code="USD",
    ),
    VolumeSurgeTarget(
        ticker="XLE",
        name="Energy Select Sector SPDR Fund",
        theme="에너지 — 원유/유틸리티",
        source_type="YAHOO_GLOBAL_XLE",
        threshold=2.0,
        currency_code="USD",
    ),
)

# 최종 모니터링 대상 = 한국 ETF + 한국 대형주 + 글로벌 ETF
VOLUME_SURGE_TARGETS: tuple[VolumeSurgeTarget, ...] = (
    _KOREAN_ETF_TARGETS + _KOREAN_STOCK_TARGETS + _GLOBAL_ETF_TARGETS
)

# 하위 호환: 기존 코드에서 `ETF_TARGETS` 로 참조하던 경우를 위한 alias.
ETF_TARGETS = VOLUME_SURGE_TARGETS

# 이동평균 윈도우(거래일 기준). 20거래일 ≒ 약 4주.
_MA_WINDOW = 20

# `period` 인자: 20일 이동평균 + 장기 시계열. 1y 권장(BRONZE 시계열 확충).
_HISTORY_PERIOD = "1y"

# IP 차단 방어용 티커 간 sleep. 16개 티커 × 0.5초 = 약 8초 — 운영에 무리 없는 수준.
_INTER_TICKER_SLEEP_SEC = 0.5


def _to_kst(ts: Timestamp) -> datetime:
    """`pandas.Timestamp` → tz-aware KST datetime."""
    py_dt = ts.to_pydatetime()
    if py_dt.tzinfo is None:
        return py_dt.replace(tzinfo=_KST)
    return py_dt.astimezone(_KST)


def _vwap_approx(high: float, low: float, close: float) -> float:
    """HLCC/3 근사 — 진짜 VWAP 대비 오차 1~5% 수준(틱 없이 가장 합리적인 근사)."""
    return (high + low + close) / 3.0


def _drop_trailing_nan(hist: DataFrame) -> DataFrame:
    """yfinance 가 한국 시장 마감 전 마지막 행을 NaN 으로 주는 경우 대비.

    필수 컬럼(`Close`, `Volume`) 중 하나라도 NaN 인 후행 행을 모두 잘라낸다.
    중간 행에 들어간 NaN(휴장 등)은 보존한다.
    """
    if hist is None or hist.empty:
        return hist

    last_valid_idx = -1
    for i in range(len(hist) - 1, -1, -1):
        row = hist.iloc[i]
        ok = True
        for col in _REQUIRED_COLS:
            if col not in hist.columns:
                ok = False
                break
            val = row[col]
            if val is None or (isinstance(val, float) and math.isnan(val)):
                ok = False
                break
        if ok:
            last_valid_idx = i
            break

    if last_valid_idx < 0:
        return hist.iloc[0:0]  # 모두 NaN — 빈 프레임 반환
    return hist.iloc[: last_valid_idx + 1]


def _compute_inflow_dto(
    target: VolumeSurgeTarget,
    hist: DataFrame,
) -> EconomicCollectDto | None:
    """마지막 유효 거래일의 거래량이 임계값을 넘으면 Bronze DTO 1건 반환."""
    hist = _drop_trailing_nan(hist)

    if hist is None or hist.empty or len(hist) < _MA_WINDOW + 1:
        logger.warning(
            "Yahoo[%s] 데이터 부족 — rows=%s (필요 >= %s)",
            target.ticker,
            0 if hist is None else len(hist),
            _MA_WINDOW + 1,
        )
        return None

    last = hist.iloc[-1]
    last_ts: Timestamp = hist.index[-1]  # type: ignore[assignment]

    last_volume = float(last["Volume"])
    if last_volume <= 0:
        return None

    # 이전 20일 평균 (마지막 행 제외 → 더 보수적)
    prev_window = hist.iloc[-(_MA_WINDOW + 1):-1]
    avg_volume = float(prev_window["Volume"].mean())
    if avg_volume <= 0 or math.isnan(avg_volume):
        return None

    volume_ratio = last_volume / avg_volume
    if volume_ratio < target.threshold:
        logger.debug(
            "Yahoo[%s] 임계값 미달 — ratio=%.2f < %.2f",
            target.ticker,
            volume_ratio,
            target.threshold,
        )
        return None

    high = float(last["High"])
    low = float(last["Low"])
    close = float(last["Close"])
    vwap = _vwap_approx(high, low, close)
    inflow_amount = int(round(last_volume * vwap))

    trade_date_local = _to_kst(last_ts)
    date_str = trade_date_local.strftime("%Y-%m-%d")

    currency_label = "원" if target.currency_code == "KRW" else "달러"
    raw_title = (
        f"{target.name}({target.ticker}) 거래량 {volume_ratio:.2f}배 급증 "
        f"({date_str}, 추정 유입액 {inflow_amount:,}{currency_label})"
    )

    source_url = (
        f"https://finance.yahoo.com/quote/{target.ticker}/history?period1={date_str}"
    )

    raw_metadata: dict[str, object] = {
        "ticker": target.ticker,
        "asset_name": target.name,
        "theme": target.theme,
        "trade_date": date_str,
        "volume": int(last_volume),
        "avg_volume_20d": int(avg_volume),
        "volume_ratio": round(volume_ratio, 3),
        "threshold": target.threshold,
        "ohlc": {
            "open": float(last["Open"]),
            "high": high,
            "low": low,
            "close": close,
        },
        "vwap_approx": round(vwap, 4),
        "inflow_amount": inflow_amount,
        "inflow_currency": target.currency_code,
        "calculation_method": "volume * (high + low + close) / 3",
    }

    return EconomicCollectDto(
        source_type=target.source_type[:50],
        source_url=source_url,
        raw_title=raw_title[:500],
        investor_name=None,
        target_company_or_fund=target.name[:255],
        investment_amount=inflow_amount,
        currency=target.currency_code,
        raw_metadata=raw_metadata,
        published_at=trade_date_local,
    )


class YahooFinanceEtfCollector:
    """거래량 급증(Volume Surge) Collector — 한국 ETF/대형주 + 글로벌 ETF 통합.

    동작:
      1) `VOLUME_SURGE_TARGETS` 각 자산에 대해 시세 다운로드(기본 ``period=1y``)
      2) NaN 후행 행 제거 (한국 시장 마감 전 호출 대비)
      3) 이전 20일 평균 거래량 대비 마지막 거래일 거래량 비율 계산
      4) 자산별 멀티 레벨 임계값(`threshold`) 초과 시 Bronze DTO 1건 생성
      5) 유입 금액은 VWAP 근사 (`volume × (high+low+close)/3`) 로 추정

    IP 차단 방어:
      - 티커 간 `_INTER_TICKER_SLEEP_SEC` 만큼 대기
      - `asyncio.to_thread` 안에서 동기 `time.sleep` 사용 (이벤트 루프 비차단)

    실패 격리:
      - 특정 티커 다운로드/계산 실패는 logger.exception 으로 흡수
      - 다른 티커 처리에는 영향 없음
    """

    def __init__(
        self,
        targets: tuple[VolumeSurgeTarget, ...] = VOLUME_SURGE_TARGETS,
        *,
        inter_ticker_sleep_sec: float = _INTER_TICKER_SLEEP_SEC,
    ):
        self._targets = targets
        self._sleep_sec = inter_ticker_sleep_sec

    def collect_sync(
        self, *, period: str | None = None
    ) -> tuple[list[EconomicCollectDto], int]:
        """동기 수집 — yfinance 가 동기 라이브러리이므로 스레드 오프로딩 권장.

        Args:
            period: ``yfinance`` ``history(period=...)`` 인자. None 이면 모듈 기본(1y).

        Returns:
            (감지된 DTO 리스트, 임계값 미달/실패로 스킵된 자산 수)
        """
        p = period or _HISTORY_PERIOD
        out: list[EconomicCollectDto] = []
        skipped = 0

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
                    "Yahoo[%s] history 다운로드 실패 — 다음 티커로 진행", target.ticker
                )
                skipped += 1
                continue

            try:
                dto = _compute_inflow_dto(target, hist)
            except Exception:
                logger.exception(
                    "Yahoo[%s] 급증 계산 중 예외 — 다음 티커로 진행", target.ticker
                )
                skipped += 1
                continue

            if dto is None:
                skipped += 1
                continue

            out.append(dto)

        logger.info(
            "Yahoo Volume Surge 수집 완료: %s개 신호 / %s개 스킵 (총 %s 자산)",
            len(out),
            skipped,
            len(self._targets),
        )
        return out, skipped

    def collect_surge_history_sync(
        self, *, period: str | None = None
    ) -> tuple[list[EconomicCollectDto], int]:
        """기간 내 **모든 거래일**에 대해 거래량 급증 신호를 스캔 (시계열 Backfill).

        일일 스케줄 잡은 ``collect_sync`` 만 호출해도 되고, 초기 적재 시에만
        본 메서드를 사용하면 과거 급증일이 ``source_url`` 기준으로 누적된다.

        Returns:
            (DTO 리스트, 티커 단위 완전 실패 수)
        """
        p = period or _HISTORY_PERIOD
        out: list[EconomicCollectDto] = []
        failed_tickers = 0

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
                    "Yahoo[%s] history(backfill) 다운로드 실패", target.ticker
                )
                failed_tickers += 1
                continue

            hist = _drop_trailing_nan(hist)
            if hist is None or hist.empty or len(hist) < _MA_WINDOW + 2:
                failed_tickers += 1
                continue

            for end_idx in range(_MA_WINDOW, len(hist)):
                sub = hist.iloc[: end_idx + 1]
                try:
                    dto = _compute_inflow_dto(target, sub)
                except Exception:
                    continue
                if dto is not None:
                    out.append(dto)

        logger.info(
            "Yahoo Volume Surge **history** scan: %s signals, failed_tickers=%s period=%s",
            len(out),
            failed_tickers,
            p,
        )
        return out, failed_tickers

    async def collect(
        self, *, backfill: bool = False, period: str | None = None
    ) -> tuple[list[EconomicCollectDto], int]:
        def _run() -> tuple[list[EconomicCollectDto], int]:
            if backfill:
                return self.collect_surge_history_sync(period=period)
            return self.collect_sync(period=period)

        return await asyncio.to_thread(_run)
