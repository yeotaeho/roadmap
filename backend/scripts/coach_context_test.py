# 코치 컨텍스트 조립·롤링 요약 트리거 순수 단위 테스트(무DB·무LLM)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.ai_coach.hub.services.coach_context import (
    build_llm_messages,
    select_to_summarize,
    split_history,
)

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
    check("임계 이하 미트리거", select_to_summarize(24, 20, 24) is False)
    check("임계 초과 트리거", select_to_summarize(25, 20, 24) is True)

    msgs = [{"role": "user", "content": str(i)} for i in range(25)]
    older, recent = split_history(msgs, 20)
    check("older 5건", len(older) == 5)
    check("recent 20건", len(recent) == 20)
    check("recent 끝 유지", recent[-1]["content"] == "24")

    # 짧은 대화 — 요약 없음, 전체 주입
    out = build_llm_messages("SYS", None, [{"role": "user", "content": "안녕"}], "새 질문")
    check("system 선두", out[0] == {"role": "system", "content": "SYS"})
    check("요약없으면 요약블록 없음", all("[이전 대화 요약]" not in m["content"] for m in out))
    check("마지막 user 메시지", out[-1] == {"role": "user", "content": "새 질문"})

    # 요약 있음 — 요약 블록이 system 다음, recent 앞
    out2 = build_llm_messages("SYS", "사용자는 진로 고민 중", [{"role": "assistant", "content": "직전 답"}], "다음")
    check("요약 블록 포함", any("[이전 대화 요약]" in m["content"] and "진로 고민" in m["content"] for m in out2))
    check("recent 포함", any(m["content"] == "직전 답" for m in out2))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
