# 코치 내부 tool 팩토리 단위 테스트(무DB·무네트워크) — 스키마·라벨·read-only 계약

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.ai_coach.spokes.agents.tools.internal_tools import TOOL_LABELS, build_internal_tools

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


def run() -> int:
    tools = build_internal_tools("00000000-0000-0000-0000-000000000000")
    names = {t.name for t in tools}
    expected = {
        "get_pulse_trends", "get_gap_issues", "get_chance_matches",
        "get_sync_snapshot", "get_user_profile", "search_insights",
    }
    check("tool 6종", names == expected, str(names))
    check("전부 설명 보유", all((t.description or "").strip() for t in tools))
    check("전부 비동기", all(t.coroutine is not None for t in tools))
    check("라벨 전수", set(TOOL_LABELS.keys()) == expected)
    check("라벨 한국어", all(any("가" <= ch <= "힣" for ch in v) for v in TOOL_LABELS.values()))

    # user_id 는 클로저로 고정 — LLM 이 넘길 수 있는 인자에 user_id 가 없어야 한다(권한 상승 차단).
    for t in tools:
        schema = t.args_schema.model_json_schema() if t.args_schema else {"properties": {}}
        check(f"{t.name} 인자에 user_id 없음", "user_id" not in schema.get("properties", {}))

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
