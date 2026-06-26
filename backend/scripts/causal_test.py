# causal_chains 순수 파서(_parse_causal) 무DB 검증 테스트

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _parse_causal  # noqa: E402

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


def test_valid() -> None:
    raw = json.dumps({
        "macro_event": "미국 금리 인하 시그널 강화",
        "industry_impact": "빅테크 AI·클라우드 투자 재가속",
        "youth_chance": "AI 백엔드·보안 엔지니어 수요 확대",
    })
    out = _parse_causal(raw)
    check("macro 보존", out["macro_event"] == "미국 금리 인하 시그널 강화")
    check("industry 보존", out["industry_impact"] == "빅테크 AI·클라우드 투자 재가속")
    check("youth 보존", out["youth_chance"] == "AI 백엔드·보안 엔지니어 수요 확대")


def test_incomplete() -> None:
    # youth_chance 누락 → 무효(전부 None)
    raw = json.dumps({"macro_event": "x", "industry_impact": "y", "youth_chance": None})
    out = _parse_causal(raw)
    check("불완전→macro None", out["macro_event"] is None)
    check("불완전→youth None", out["youth_chance"] is None)

    # 빈 문자열도 무효
    raw2 = json.dumps({"macro_event": "x", "industry_impact": "  ", "youth_chance": "z"})
    check("빈문자열 industry→무효", _parse_causal(raw2)["macro_event"] is None)


def test_bad() -> None:
    check("bad json→None", _parse_causal("nope")["macro_event"] is None)
    check("None→None", _parse_causal(None)["youth_chance"] is None)
    check("비dict→None", _parse_causal(json.dumps([1, 2]))["macro_event"] is None)


def test_truncate() -> None:
    raw = json.dumps({"macro_event": "가" * 400, "industry_impact": "나", "youth_chance": "다"})
    out = _parse_causal(raw)
    check("255자 컷", out["macro_event"] is not None and len(out["macro_event"]) == 255)


def main() -> int:
    test_valid()
    test_incomplete()
    test_bad()
    test_truncate()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
