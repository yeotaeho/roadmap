# 코치 웹 tool 라이브 검증 — Tavily·WaterCrawl 실호출 + 코치 1턴에서 web_search 사용 확인

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 콘솔에서 이모지·특수문자 출력 시 크래시 방지

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
    from domain.ai_coach.spokes.agents.tools.web_tools import build_web_tools

    # 1) 웹 tool 2종 실호출
    tools = {t.name: t for t in build_web_tools()}
    check("웹 tool 2종 활성", set(tools) == {"web_search", "fetch_url"}, str(set(tools)))

    search = await tools["web_search"].ainvoke({"query": "2026년 AI 개발자 채용 시장 동향"})
    ok_search = isinstance(search, dict) and bool(search.get("results"))
    check("Tavily 검색 결과 수신", ok_search, str(search)[:200])
    first_url = search["results"][0]["url"] if ok_search else None
    if ok_search:
        print(f"    → {len(search['results'])}건, 첫 결과: {first_url}")
        check("결과 행마다 출처 url", all(r.get("url") for r in search["results"]))

    if first_url:
        page = await tools["fetch_url"].ainvoke({"url": first_url})
        ok_page = isinstance(page, dict) and len(page.get("content") or "") > 0
        check("WaterCrawl 본문 수신", ok_page, str(page)[:200])
        if ok_page:
            print(f"    → 본문 {len(page['content'])}자 (truncated={page.get('truncated')})")

    # 2) 코치 1턴 — 최신성 질문에 web_search 가 실제로 발동하는지
    async with AsyncSessionLocal() as db:
        sid = await CoachService(db).get_or_create_session(user_id)
    types, tool_names, text = [], [], ""
    async with AsyncSessionLocal() as db:
        svc = CoachService(db)
        async for sse in svc.stream_sse(
            user_id, sid, "최근 AI 개발자 채용 시장 뉴스를 웹에서 찾아서 요약해줘."
        ):
            obj = json.loads(sse.removeprefix("data: ").strip())
            types.append(obj.get("type"))
            if obj.get("type") == "tool_call":
                tool_names.append(obj.get("name"))
                print(f"    [tool_call] {obj.get('name')}")
            if obj.get("type") == "delta":
                text += obj.get("content") or ""
    check("스트림 done 종료", bool(types) and types[-1] == "done", str(types[-3:]))
    check("web_search 발동", "web_search" in tool_names, str(tool_names))
    check("텍스트 응답 수신", len(text) > 20, text[:120])
    check("에러 이벤트 없음", "error" not in types)
    print(f"\n--- 응답 미리보기 ---\n{text[:500]}\n")

    print(f"합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user-id", required=True)
    a = p.parse_args()
    sys.exit(asyncio.run(main(a.user_id)))
