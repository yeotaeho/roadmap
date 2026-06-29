# TimesFM 시장 시계열 예측 래퍼 — 티커 close_price 배치 예측 → (수익률%, 분위수 밴드폭)

from __future__ import annotations

import logging
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


class Forecaster(Protocol):
    """티커 시계열 → (예측 수익률%, 상대 밴드폭) 매핑. 테스트는 Fake 로 대체한다."""

    def forecast_returns(
        self, series_by_ticker: dict[str, list[float]], horizon: int
    ) -> dict[str, tuple[float, float]]:
        ...


def point_to_return(last_close: float, point_path) -> float:
    """예측 마지막 스텝 대비 % 수익률. last_close<=0 이면 0(가드)."""
    if last_close <= 0:
        return 0.0
    return (float(point_path[-1]) - last_close) / last_close * 100.0


def quantile_to_band_rel(point_path, quantile_path, lo_idx: int, hi_idx: int) -> float:
    """마지막 스텝 (q_hi − q_lo)/|point| 상대 밴드폭. point 0 이면 0(가드)."""
    last_point = abs(float(point_path[-1]))
    if last_point <= 0:
        return 0.0
    q = np.asarray(quantile_path)
    return max(0.0, (float(q[-1, hi_idx]) - float(q[-1, lo_idx])) / last_point)


class FakeForecaster:
    """결정론적 주입용 — 무모델 테스트·E2E 스모크에서 TimesfmForecaster 를 대체한다."""

    def __init__(self, mapping: dict[str, tuple[float, float]]) -> None:
        self._mapping = mapping

    def forecast_returns(
        self, series_by_ticker: dict[str, list[float]], horizon: int
    ) -> dict[str, tuple[float, float]]:
        return {t: self._mapping[t] for t in series_by_ticker if t in self._mapping}


class TimesfmForecaster:
    """TimesFM 2.5(torch) lazy 싱글톤 래퍼. 모든 티커를 단일 forecast 호출로 배치한다."""

    _DEFAULT_REPO = "google/timesfm-2.5-200m-pytorch"
    # 분위수 10열 중 내부 밴드 인덱스(0.1·0.9 근사). Step 4 에서 실제 배열로 확인·조정.
    _Q_LO_IDX = 1
    _Q_HI_IDX = 9

    def __init__(
        self,
        repo_id: str | None = None,
        max_context: int = 512,
        min_history: int = 64,
    ) -> None:
        self._repo_id = repo_id or self._DEFAULT_REPO
        self._max_context = max_context
        self._min_history = min_history
        self._model = None

    def _ensure(self, horizon: int) -> None:
        if self._model is not None:
            return
        import timesfm

        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(self._repo_id)
        model.compile(
            timesfm.ForecastConfig(
                max_context=self._max_context,
                max_horizon=max(64, horizon),
                normalize_inputs=True,
                use_continuous_quantile_head=True,
                fix_quantile_crossing=True,
            )
        )
        self._model = model
        logger.info("[forecast] TimesFM loaded repo=%s", self._repo_id)

    def forecast_returns(
        self, series_by_ticker: dict[str, list[float]], horizon: int
    ) -> dict[str, tuple[float, float]]:
        usable = {
            t: s for t, s in series_by_ticker.items() if len(s) >= self._min_history
        }
        if not usable:
            return {}
        self._ensure(horizon)
        tickers = list(usable.keys())
        inputs = [np.asarray(usable[t], dtype=np.float32) for t in tickers]
        point, quantile = self._model.forecast(horizon=horizon, inputs=inputs)
        point = np.asarray(point)
        quantile = np.asarray(quantile)
        out: dict[str, tuple[float, float]] = {}
        for i, t in enumerate(tickers):
            ret = point_to_return(float(usable[t][-1]), point[i])
            band = quantile_to_band_rel(point[i], quantile[i], self._Q_LO_IDX, self._Q_HI_IDX)
            if np.isfinite(ret) and np.isfinite(band):
                out[t] = (ret, band)
        return out

    def unload(self) -> None:
        """배치 종료 후 모델 해제 — API 프로세스 영구 상주 회피."""
        self._model = None
