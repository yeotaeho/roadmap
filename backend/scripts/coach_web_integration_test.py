# 코치 웹 tool 통합 테스트(무DB·무네트워크) — tool 합성·라벨 병합·프롬프트 라우팅 지침

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.config.settings import get_settings
from domain.ai_coach.hub.services.coach_service import _COACH_SYSTEM_PROMPT, CoachService
from domain.ai_coach.spokes.agents.tools.internal_tools import TOOL_LABELS
from domain.ai_coach.spokes.agents.tools.web_tools import WEB_TOOL_LABELS

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
    svc = CoachService(None)  # DB 세션은 tool 구성에 불필요.
    tools = svc._build_tools("00000000-0000-0000-0000-000000000000")
    names = {t.name for t in tools}

    internal = {
        "get_pulse_trends", "get_gap_issues", "get_chance_matches",
        "get_sync_snapshot", "get_user_profile", "search_insights",
    }
    check("내부 6종 항상 포함", internal <= names, str(names))

    settings = get_settings()
    if getattr(settings, "tavily_api_key", None):
        check("Tavily 키 존재 → web_search 포함", "web_search" in names)
    else:
        check("Tavily 키 부재 → web_search 제외", "web_search" not in names)
    if getattr(settings, "watercrawl_api_key", None):
        check("WaterCrawl 키 존재 → fetch_url 포함", "fetch_url" in names)
    else:
        check("WaterCrawl 키 부재 → fetch_url 제외", "fetch_url" not in names)

    # 라벨 계약 — 이름 충돌 없음 + coach_graph 병합 매핑이 양쪽을 커버.
    check("라벨 이름 충돌 없음", set(TOOL_LABELS) & set(WEB_TOOL_LABELS) == set())
    from domain.ai_coach.spokes.infra import coach_graph

    merged = getattr(coach_graph, "_ALL_TOOL_LABELS")
    check("병합 라벨이 내부+웹 전수 커버", set(merged) == set(TOOL_LABELS) | set(WEB_TOOL_LABELS))

    # 시스템 프롬프트 — 웹 라우팅·출처 지침이 실제로 들어갔는지.
    check("프롬프트에 web_search 라우팅", "web_search" in _COACH_SYSTEM_PROMPT)
    check("프롬프트에 fetch_url 라우팅", "fetch_url" in _COACH_SYSTEM_PROMPT)
    check("프롬프트에 출처 URL 지침", "출처 URL" in _COACH_SYSTEM_PROMPT)

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
