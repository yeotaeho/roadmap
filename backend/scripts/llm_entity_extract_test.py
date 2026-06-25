# 신호 추출 응답 파서(_parse_extract) 무네트워크 결정론적 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _parse_extract  # noqa: E402

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
    r = _parse_extract('{"signal_topic": "LLM 추론 칩", "extracted_keywords": ["LLM", "칩", "추론"], "confidence": 0.8}')
    check("토픽 파싱", r["signal_topic"] == "LLM 추론 칩")
    check("키워드 파싱", r["extracted_keywords"] == ["LLM", "칩", "추론"])
    check("confidence 파싱", abs(r["confidence"] - 0.8) < 1e-9)


def test_no_topic() -> None:
    r1 = _parse_extract('{"signal_topic": null, "extracted_keywords": ["x"], "confidence": 0.9}')
    check("null 토픽 → None", r1["signal_topic"] is None)
    check("토픽 None 이면 confidence 0", r1["confidence"] == 0.0)
    r2 = _parse_extract('{"signal_topic": "  ", "extracted_keywords": []}')
    check("공백 토픽 → None", r2["signal_topic"] is None)


def test_keywords_edge() -> None:
    r1 = _parse_extract('{"signal_topic": "t", "extracted_keywords": "not a list"}')
    check("키워드 비-리스트 → []", r1["extracted_keywords"] == [])
    r2 = _parse_extract('{"signal_topic": "t"}')
    check("키워드 누락 → []", r2["extracted_keywords"] == [])
    big = '{"signal_topic": "t", "extracted_keywords": [' + ",".join(f'"k{i}"' for i in range(20)) + "]}"
    check("키워드 최대 10개로 절단", len(_parse_extract(big)["extracted_keywords"]) == 10)
    r3 = _parse_extract('{"signal_topic": "t", "extracted_keywords": ["a", "", "  ", "b"]}')
    check("빈 키워드 제거", r3["extracted_keywords"] == ["a", "b"])


def test_malformed() -> None:
    check("잘못된 JSON → None", _parse_extract("nope")["signal_topic"] is None)
    check("None 입력 → None", _parse_extract(None)["signal_topic"] is None)
    check("비-객체 → None", _parse_extract("[1,2]")["signal_topic"] is None)


def main() -> int:
    for fn in (test_valid, test_no_topic, test_keywords_edge, test_malformed):
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
