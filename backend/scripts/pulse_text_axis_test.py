# economic_text·discourse 축의 가중치 등록·통약·융합 무네트워크 결정론적 테스트

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

from domain.market_insight.hub.repositories.pulse_repository import _normalize_axes  # noqa: E402
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


def test_weights_registered() -> None:
    check("economic_text 가중치=1.0", DEFAULT_AXIS_WEIGHTS.get("economic_text") == 1.0)
    check("discourse 가중치=0.5", DEFAULT_AXIS_WEIGHTS.get("discourse") == 0.5)


def test_text_axis_normalize_band() -> None:
    # 새 텍스트 축도 축별로 독립 0~100 band 정규화.
    sigs = [
        AxisSignal("ai-data", D, "discourse", 10.0),
        AxisSignal("bio-health", D, "discourse", 2.0),
        AxisSignal("ai-data", D, "economic_text", 4.0),
        AxisSignal("fintech", D, "economic_text", 1.0),
    ]
    out = _normalize_axes(sigs)
    vals = {(s.sector_slug, s.axis): s.value for s in out}
    check("정규화 후 0~100", all(0 <= s.value <= 100 for s in out))
    check("discourse max=100(ai)", vals[("ai-data", "discourse")] == 100.0)
    check("discourse min=0(bio)", vals[("bio-health", "discourse")] == 0.0)
    check("economic_text max=100(ai)", vals[("ai-data", "economic_text")] == 100.0)
    check("economic_text min=0(fintech)", vals[("fintech", "economic_text")] == 0.0)


def test_text_axis_fuse_weight() -> None:
    # 통약(각 축 단일값 → 50 중립) 후 discourse(0.5)는 economic_text(1.0)의 절반 기여.
    sigs = _normalize_axes(
        [
            AxisSignal("ai-data", D, "economic_text", 100.0),
            AxisSignal("ai-data", D, "discourse", 100.0),
        ]
    )
    fused = fuse_signals(sigs, DEFAULT_AXIS_WEIGHTS)
    # 50*1.0(economic_text) + 50*0.5(discourse) = 75
    check("융합값 = economic_text(50)+discourse(25)=75", abs(fused[0].raw_signal_value - 75.0) < 1e-6)


def main() -> int:
    for fn in (test_weights_registered, test_text_axis_normalize_band, test_text_axis_fuse_weight):
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
