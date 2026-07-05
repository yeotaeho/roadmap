# 코치 읽기 계약(read_for_coach) 셰이핑 순수 단위 테스트(무DB) — 민감정보 차단 확인

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.user_intelligence.hub.services.consult_memory_service import shape_for_coach

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
    model = {"riasec": {"top_codes": ["I", "A"]}, "bigFive": None, "narrativeSummary": "탐구형."}
    evidence = [
        {"dimension": "like", "content": f"근거{i}", "confidence": 0.5 + i * 0.05, "is_sensitive": False}
        for i in range(10)
    ]
    out = shape_for_coach(model, evidence, ["요약1", "요약2", "요약3", "요약4"])
    check("selfModel 그대로", out["selfModel"] == model)
    check("근거 최대 8개", len(out["evidence"]) == 8)
    check("confidence 내림차순", out["evidence"][0]["content"] == "근거9")
    check("근거 필드 축소(dimension·content만)", set(out["evidence"][0].keys()) == {"dimension", "content"})
    check("요약 최대 3개", len(out["recentConsultSummaries"]) == 3)

    # 방어선: 민감 행이 섞여 들어와도 셰이핑 단계에서 한 번 더 걸러낸다.
    leaked = [{"dimension": "constraint", "content": "민감", "confidence": 0.9, "is_sensitive": True}]
    out2 = shape_for_coach(model, leaked, [])
    check("민감 근거 2차 차단", out2["evidence"] == [])

    out3 = shape_for_coach(None, [], [])
    check("빈 입력 안전", out3["selfModel"] is None and out3["evidence"] == [])

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
