# crossover_metrics 순수 조립 함수(assemble_crossover) 무DB 검증 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.crossover_metrics import assemble_crossover  # noqa: E402

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


def test_crossover_detected() -> None:
    rows = [
        {"bucket": "2026-01", "legacy_value": 60, "emerging_value": 40},  # diff -20
        {"bucket": "2026-02", "legacy_value": 55, "emerging_value": 50},  # diff -5
        {"bucket": "2026-03", "legacy_value": 50, "emerging_value": 58},  # diff +8 → 부호 전환
    ]
    out = assemble_crossover(rows, "전통", "신흥")
    flags = {s["bucket"]: s["is_crossover"] for s in out["series"]}
    check("교차점=2026-03", flags["2026-03"] is True)
    check("이전 버킷 비교차", flags["2026-01"] is False and flags["2026-02"] is False)
    check("라벨 보존", out["legacy_label"] == "전통" and out["emerging_label"] == "신흥")
    check("값 보존", out["series"][0]["legacy_value"] == 60 and out["series"][0]["emerging_value"] == 40)


def test_no_crossover() -> None:
    rows = [
        {"bucket": "a", "legacy_value": 40, "emerging_value": 60},
        {"bucket": "b", "legacy_value": 42, "emerging_value": 58},
    ]
    out = assemble_crossover(rows, "전통", "신흥")
    check("교차 없음", all(not s["is_crossover"] for s in out["series"]))


def test_none_safe() -> None:
    rows = [
        {"bucket": "a", "legacy_value": None, "emerging_value": 50},
        {"bucket": "b", "legacy_value": 40, "emerging_value": 60},
    ]
    out = assemble_crossover(rows, "전통", "신흥")
    check("None 버킷 비교차", out["series"][0]["is_crossover"] is False)
    check("None 보존", out["series"][0]["legacy_value"] is None)
    check("이후 버킷 비교차(이전 diff 없음)", out["series"][1]["is_crossover"] is False)


def test_empty() -> None:
    out = assemble_crossover([], "전통", "신흥")
    check("빈 series", out["series"] == [])
    check("빈 입력도 라벨", out["legacy_label"] == "전통")


def main() -> int:
    test_crossover_detected()
    test_no_crossover()
    test_none_safe()
    test_empty()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
