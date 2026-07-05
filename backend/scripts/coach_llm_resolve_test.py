# 코치 LLM 리졸버(fail-loud) 순수 단위 테스트(무DB·무네트워크)

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.llm.provider import resolve_coach_llm

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
    s = SimpleNamespace(anthropic_api_key="sk-ant-test", coach_llm_model="claude-sonnet-5")
    key, model = resolve_coach_llm(s)
    check("키·모델 반환", key == "sk-ant-test" and model == "claude-sonnet-5")

    s2 = SimpleNamespace(anthropic_api_key=None, coach_llm_model="claude-sonnet-5")
    try:
        resolve_coach_llm(s2)
        check("키 없으면 fail-loud", False, "예외 미발생")
    except RuntimeError as e:
        check("키 없으면 fail-loud", "ANTHROPIC_API_KEY" in str(e))

    s3 = SimpleNamespace(anthropic_api_key="k", coach_llm_model="")
    _, model3 = resolve_coach_llm(s3)
    check("모델 미지정 시 기본값", model3 == "claude-sonnet-5")

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
