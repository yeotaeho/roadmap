# 상담 프롬프트·조향 지침 단정 — 성향 파악 주임무·ideation 금지·성향요약 그라운딩·옛 드리프트 문구 부재.

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.llm.client import _CONSULT_SYSTEM_PROMPT

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
    p = _CONSULT_SYSTEM_PROMPT
    check("주임무=성향/성격 파악", ("RIASEC" in p and "Big Five" in p) and "어떤 사람인지" in p, p[:120])
    check("ideation 금지", ("아이디어" in p and "브레인스토밍" in p), p)
    check("코치 위임 안내", "로드맵 코치가" in p, p)
    check("성향요약 그라운딩", "성향 지도" in p and "쌓이면" in p, p)
    check("단호하되 따뜻", "주도적" in p and ("단호" in p), p)
    check("옛 드리프트 문구 부재", "진로의 방향을 함께 발견" not in p, p)
    check("민감 캐묻기 금지 유지", "민감" in p and "캐묻지" in p, p)
    check("배경 기억 비지시 유지", "배경 기억" in p and "단정" in p, p)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
