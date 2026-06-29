# LLM 섹터 분류 응답 파서(_parse_classification) 무네트워크 결정론적 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _parse_classification  # noqa: E402

SECTORS = ["ai-data", "semiconductor", "bio-health", "fintech"]

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
    r = _parse_classification('{"sector_slug": "ai-data", "confidence": 0.9}', SECTORS)
    check("유효 슬러그 파싱", r["sector_slug"] == "ai-data")
    check("유효 confidence 파싱", abs(r["confidence"] - 0.9) < 1e-9)


def test_unknown_and_out_of_list() -> None:
    r1 = _parse_classification('{"sector_slug": "unknown", "confidence": 0.8}', SECTORS)
    check("목록 외 unknown → None", r1["sector_slug"] is None)
    check("None 이면 confidence 0", r1["confidence"] == 0.0)
    r2 = _parse_classification('{"sector_slug": "robotics", "confidence": 0.7}', SECTORS)
    check("목록 외 슬러그 → None", r2["sector_slug"] is None)
    r3 = _parse_classification('{"sector_slug": null, "confidence": 0.5}', SECTORS)
    check("명시적 null → None", r3["sector_slug"] is None)


def test_confidence_edge() -> None:
    r1 = _parse_classification('{"sector_slug": "fintech"}', SECTORS)
    check("confidence 누락 → 0.0", r1["confidence"] == 0.0)
    check("confidence 누락이어도 슬러그 유지", r1["sector_slug"] == "fintech")
    r2 = _parse_classification('{"sector_slug": "fintech", "confidence": 1.5}', SECTORS)
    check("confidence 상한 클램프 1.0", r2["confidence"] == 1.0)
    r3 = _parse_classification('{"sector_slug": "fintech", "confidence": -0.3}', SECTORS)
    check("confidence 하한 클램프 0.0", r3["confidence"] == 0.0)


def test_malformed() -> None:
    check("잘못된 JSON → None", _parse_classification("not json", SECTORS)["sector_slug"] is None)
    check("None 입력 → None", _parse_classification(None, SECTORS)["sector_slug"] is None)
    check("비-객체 JSON(배열) → None", _parse_classification("[1,2]", SECTORS)["sector_slug"] is None)
    check("비-객체 JSON(숫자) → None", _parse_classification("5", SECTORS)["sector_slug"] is None)
    r = _parse_classification("not json", SECTORS)
    check("파싱 실패 감성 None·점수 0", r["sentiment"] is None and r["sentiment_score"] == 0.0)


def test_sentiment() -> None:
    r1 = _parse_classification(
        '{"sector_slug": "ai-data", "confidence": 0.9, "sentiment": "긍정", "sentiment_score": 0.8}', SECTORS
    )
    check("감성 긍정 파싱", r1["sentiment"] == "긍정")
    check("감성 점수 파싱", abs(r1["sentiment_score"] - 0.8) < 1e-9)
    r2 = _parse_classification(
        '{"sector_slug": "fintech", "confidence": 0.7, "sentiment": "부정", "sentiment_score": -0.9}', SECTORS
    )
    check("감성 부정 음수 점수", abs(r2["sentiment_score"] + 0.9) < 1e-9)
    r3 = _parse_classification(
        '{"sector_slug": "fintech", "confidence": 0.7, "sentiment": "불명", "sentiment_score": 0.5}', SECTORS
    )
    check("감성 닫힌집합 외 → None", r3["sentiment"] is None)
    check("감성 None 이면 점수 0", r3["sentiment_score"] == 0.0)
    r4 = _parse_classification(
        '{"sector_slug": "fintech", "confidence": 0.7, "sentiment": "긍정", "sentiment_score": 5}', SECTORS
    )
    check("감성 점수 상한 클램프 1.0", r4["sentiment_score"] == 1.0)
    r5 = _parse_classification(
        '{"sector_slug": "fintech", "confidence": 0.7, "sentiment": "부정", "sentiment_score": -5}', SECTORS
    )
    check("감성 점수 하한 클램프 -1.0", r5["sentiment_score"] == -1.0)
    r6 = _parse_classification('{"sector_slug": "ai-data", "confidence": 0.9}', SECTORS)
    check("감성 누락 → None", r6["sentiment"] is None)
    check("감성 누락 점수 0", r6["sentiment_score"] == 0.0)


def main() -> int:
    for fn in (test_valid, test_unknown_and_out_of_list, test_confidence_edge, test_malformed, test_sentiment):
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
