# 추천 설명 잡 배선 스모크 — 파이프라인 마지막 스텝 등록·잡 callable (LLM 무호출).

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.scheduler import _REFINE_PIPELINE, _job_recommend_explain

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
    names = [n for n, _ in _REFINE_PIPELINE]
    check("마지막 스텝 recommend_explain", names[-1] == "recommend_explain", str(names))
    check("sync_refine 뒤에 위치", names.index("recommend_explain") > names.index("sync_refine"))
    check("잡 callable", callable(_job_recommend_explain))
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
