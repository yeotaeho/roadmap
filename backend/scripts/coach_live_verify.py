# 코치 라이브 검증 — 실 DB tool 6종 반환 + Sonnet tool-calling 1턴 스트림 실동작 확인

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

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


async def main(user_id: str) -> int:
    from core.database import AsyncSessionLocal
    from domain.ai_coach.hub.services.coach_service import CoachService
    from domain.ai_coach.spokes.agents.tools.internal_tools import build_internal_tools

    # 1) tool 6종 실 DB 반환
    tools = build_internal_tools(user_id)
    for t in tools:
        try:
            args = {"query": "요즘 유망한 분야"} if t.name == "search_insights" else {}
            result = await t.ainvoke(args)
            check(f"tool {t.name} 반환", isinstance(result, dict), str(result)[:120])
            print(f"    → {str(result)[:200]}")
        except Exception as e:
            check(f"tool {t.name} 반환", False, str(e))

    # 2) 코치 1턴 스트림 — tool_call 발생 + 텍스트 응답
    async with AsyncSessionLocal() as db:
        svc = CoachService(db)
        sid = await svc.get_or_create_session(user_id)
    types: list[str] = []
    text = ""
    async with AsyncSessionLocal() as db:
        svc = CoachService(db)
        async for sse in svc.stream_sse(user_id, sid, "요즘 시장에서 나한테 맞는 방향이 뭘까?"):
            import json as _json

            obj = _json.loads(sse.removeprefix("data: ").strip())
            types.append(obj.get("type"))
            if obj.get("type") == "delta":
                text += obj.get("content") or ""
            if obj.get("type") == "tool_call":
                print(f"    [tool_call] {obj.get('name')}")
    check("스트림 done 종료", types[-1] == "done")
    check("tool_call 최소 1회", "tool_call" in types, str(types[:20]))
    check("텍스트 응답 수신", len(text) > 20, text[:120])
    print(f"\n--- 응답 미리보기 ---\n{text[:500]}\n")

    print(f"합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user-id", required=True)
    a = p.parse_args()
    sys.exit(asyncio.run(main(a.user_id)))
