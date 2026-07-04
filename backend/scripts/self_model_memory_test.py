# 자기모델 배경 기억 직렬화 순수 테스트 — 신호 게이팅·정서안정성·빈 모델→빈 문자열.

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.user_intelligence.hub.services.consult_service import self_model_memory

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
    # 신호 있는 모델 — 흥미·성격·서사
    m = {
        "riasec": {"top_codes": ["I", "A"]},
        "bigFive": {"scores": {"O": 80, "C": 75, "E": 45, "A": 50, "N": 20}},
        "narrativeSummary": "탐구를 좋아하는 빌더",
    }
    s = self_model_memory(m)
    check("흥미 라벨", "탐구" in s and "예술" in s, s)
    check("성격 뚜렷 축(개방·성실)", "개방" in s or "새로움" in s, s)
    check("정서안정성(N 낮음→안정)", "안정" in s, s)
    check("중립 축 A 미포함(50)", "배려" not in s and "솔직" not in s, s)
    check("서사 포함", "탐구를 좋아하는 빌더" in s, s)
    check("배경 기억 헤더·단정금지", "배경 기억" in s, s)

    # 신호 없는 모델 → 빈 문자열
    empty = {"riasec": {"top_codes": []}, "bigFive": {"scores": {k: 50 for k in "OCEAN"}}, "narrativeSummary": None}
    check("무신호 → 빈 문자열", self_model_memory(empty) == "", repr(self_model_memory(empty)))
    check("None → 빈 문자열", self_model_memory(None) == "")
    # N 높음 → 신중(병리 아님)
    hi_n = {"riasec": {"top_codes": []}, "bigFive": {"scores": {"O": 50, "C": 50, "E": 50, "A": 50, "N": 85}}, "narrativeSummary": None}
    sn = self_model_memory(hi_n)
    check("N 높음 → 신중 서술", "신중" in sn, sn)
    check("N 높음 병리 없음", "불안" not in sn and "예민" not in sn, sn)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
