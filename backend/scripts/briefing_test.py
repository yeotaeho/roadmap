# economic_briefings 순수함수(_parse_briefing·template_briefing) 무DB 검증 테스트

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _parse_briefing  # noqa: E402
from domain.market_insight.hub.services.briefing_service import template_briefing  # noqa: E402

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


def test_parse_valid_3() -> None:
    raw = json.dumps({
        "lines": [
            {"content": "환율 상승, 해외취업 비용 증가.", "trend_icon": "UP_RIGHT"},
            {"content": "금리 동결, 대출 부담 완화.", "trend_icon": "WAVE"},
            {"content": "AI 채용 확대.", "trend_icon": "DOWN_RIGHT"},
        ]
    })
    out = _parse_briefing(raw)
    check("정상 3줄 파싱", len(out) == 3)
    check("content 보존", out[0]["content"] == "환율 상승, 해외취업 비용 증가.")
    check("icon 보존", out[0]["trend_icon"] == "UP_RIGHT" and out[2]["trend_icon"] == "DOWN_RIGHT")


def test_parse_bad_icon() -> None:
    raw = json.dumps({
        "lines": [
            {"content": "a", "trend_icon": "FOO"},
            {"content": "b", "trend_icon": "WAVE"},
            {"content": "c"},
        ]
    })
    out = _parse_briefing(raw)
    check("잘못된 icon→WAVE", out[0]["trend_icon"] == "WAVE")
    check("icon 누락→WAVE", out[2]["trend_icon"] == "WAVE")


def test_parse_too_few() -> None:
    raw = json.dumps({"lines": [{"content": "a", "trend_icon": "WAVE"}]})
    check("3줄 미만→[]", _parse_briefing(raw) == [])


def test_parse_more_than_3() -> None:
    raw = json.dumps({"lines": [{"content": f"line{i}", "trend_icon": "WAVE"} for i in range(5)]})
    check("3줄 초과→앞 3줄", len(_parse_briefing(raw)) == 3)


def test_parse_bad() -> None:
    check("bad json→[]", _parse_briefing("not json") == [])
    check("None→[]", _parse_briefing(None) == [])
    check("빈 content 포함→[]", _parse_briefing(json.dumps({"lines": [{"content": ""}, {"content": "b"}, {"content": "c"}]})) == [])


def test_template_movers() -> None:
    movers = [
        {"sector_name": "AI·데이터", "momentum_pct": 40.0},
        {"sector_name": "반도체", "momentum_pct": -8.0},
        {"sector_name": "바이오", "momentum_pct": 2.0},
    ]
    out = template_briefing(movers)
    check("movers 3개→3줄", len(out) == 3)
    check("상승 icon=UP_RIGHT", out[0]["trend_icon"] == "UP_RIGHT")
    check("하락 icon=DOWN_RIGHT", out[1]["trend_icon"] == "DOWN_RIGHT")
    check("보합 icon=WAVE", out[2]["trend_icon"] == "WAVE")


def test_template_empty() -> None:
    out = template_briefing([])
    check("빈 movers도 3줄", len(out) == 3)
    check("빈 movers 전부 WAVE", all(l["trend_icon"] == "WAVE" for l in out))


def main() -> int:
    test_parse_valid_3()
    test_parse_bad_icon()
    test_parse_too_few()
    test_parse_more_than_3()
    test_parse_bad()
    test_template_movers()
    test_template_empty()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
