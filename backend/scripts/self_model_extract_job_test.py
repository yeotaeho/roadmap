# 자기모델 추출 잡 스모크 — _job_self_model_extract 가 dict 반환(에러 없이 실행).

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.scheduler import _job_self_model_extract

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


async def run() -> int:
    res = await _job_self_model_extract()
    check("dict 반환", isinstance(res, dict), str(type(res)))
    check("sessions 키", "sessions" in res and "processed" in res, str(res))
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
