# Pulse 축간 통약(정규화)·시장축 매핑 무네트워크 결정론적 테스트

from __future__ import annotations

import os
import sys

for _k, _v in dict(
    NEON_DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
    JWT_SECRET="x",
    NAVER_CLIENT_ID="x",
    NAVER_CLIENT_SECRET="x",
    NAVER_REDIRECT_URI="x",
).items():
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date  # noqa: E402

from domain.market_insight.hub.repositories.pulse_repository import (  # noqa: E402
    _MARKET_SOURCE_MAP,
    _normalize_axes,
)
from domain.market_insight.hub.services.pulse_pipeline import (  # noqa: E402
    AxisSignal,
    DEFAULT_AXIS_WEIGHTS,
    fuse_signals,
)

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


D = date(2026, 6, 24)


def test_normalize_band() -> None:
    # 혁신 카운트(1~5)와 시장 상대유량(매우 큰 값)이 섞여도 축별로 0~100 band로 정규화.
    sigs = [
        AxisSignal("ai-data", D, "innovation", 5.0),
        AxisSignal("bio-health", D, "innovation", 1.0),
        AxisSignal("ai-data", D, "market", 5_000_000_000.0),
        AxisSignal("bio-health", D, "market", 1_000_000_000.0),
    ]
    out = _normalize_axes(sigs)
    vals = {(s.sector_slug, s.axis): s.value for s in out}
    check("정규화 후 모든 값 0~100", all(0 <= s.value <= 100 for s in out))
    # 각 축 내에서 max=100, min=0
    check("innovation 축 max=100(ai)", vals[("ai-data", "innovation")] == 100.0)
    check("innovation 축 min=0(bio)", vals[("bio-health", "innovation")] == 0.0)
    check("market 축 max=100(ai)", vals[("ai-data", "market")] == 100.0)
    check("market 축 min=0(bio)", vals[("bio-health", "market")] == 0.0)
    # 통약: 시장(50억)이 혁신(5)을 스케일로 압도하지 않음 — 동일 0~100 band
    check(
        "시장 turnover가 카운트를 압도하지 않음(동일 band)",
        vals[("ai-data", "market")] == vals[("ai-data", "innovation")],
    )


def test_span_zero_neutral() -> None:
    # 단일/동일값 축은 50(중립).
    out = _normalize_axes([AxisSignal("fintech", D, "people", 7.0)])
    check("span=0 축은 50 중립", out[0].value == 50.0)


def test_fuse_commensurate() -> None:
    # 통약된 값을 융합하면 시장과 혁신이 동등 기여(가중치 동일 1.0).
    sigs = _normalize_axes(
        [
            AxisSignal("ai-data", D, "innovation", 100.0),
            AxisSignal("ai-data", D, "market", 9_999_999_999.0),
        ]
    )
    fused = fuse_signals(sigs, DEFAULT_AXIS_WEIGHTS)
    # 두 축 모두 span=0(각 1점) → 50씩 → 가중합 50*1.0 + 50*1.0 = 100
    check("융합값 = 두 축 동등 기여(50+50)", abs(fused[0].raw_signal_value - 100.0) < 1e-6)


def test_market_source_map() -> None:
    check("ETF_AI→ai-data", _MARKET_SOURCE_MAP.get("YAHOO_ETF_AI") == "ai-data")
    check("SMH→semiconductor", _MARKET_SOURCE_MAP.get("YAHOO_GLOBAL_SMH") == "semiconductor")
    check("SBIO→bio-health", _MARKET_SOURCE_MAP.get("YAHOO_STOCK_KR_SBIO") == "bio-health")
    check("LGES→energy-climate", _MARKET_SOURCE_MAP.get("YAHOO_STOCK_KR_LGES") == "energy-climate")
    check("KFOOD→food-agri", _MARKET_SOURCE_MAP.get("YAHOO_ETF_KFOOD") == "food-agri")
    # 광범위 지수는 섹터 무귀속(skip)
    check("SPY 미매핑(skip)", _MARKET_SOURCE_MAP.get("YAHOO_GLOBAL_SPY") is None)
    check("QQQ 미매핑(skip)", _MARKET_SOURCE_MAP.get("YAHOO_GLOBAL_QQQ") is None)
    check("market 가중치 등록됨", DEFAULT_AXIS_WEIGHTS.get("market") == 1.0)


def main() -> int:
    for fn in (test_normalize_band, test_span_zero_neutral, test_fuse_commensurate, test_market_source_map):
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
