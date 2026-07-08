# 코치 액션 tool — 로드맵 딥 에이전트 생성 발주(fire-and-forget, 유일한 비조회 tool)
from __future__ import annotations

from langchain_core.tools import tool

from core.database import AsyncSessionLocal

ACTION_TOOL_LABELS: dict[str, str] = {
    "launch_roadmap_generation": "로드맵 생성 발주",
}


def build_action_tools(user_id: str) -> list:
    """user_id 클로저 고정 — LLM 인자로 user_id 를 받지 않는다(권한 상승 차단)."""

    @tool
    async def launch_roadmap_generation() -> dict:
        """사용자가 로드맵 생성·개편을 원할 때 로드맵 딥 에이전트를 발주한다. 수 분 걸리는
        백그라운드 작업이므로, 발주 후 사용자에게 '로드맵 탭에서 진행 상황을 확인하라'고 안내한다.
        이미 진행 중이면 새로 발주하지 말고 그 사실을 알린다."""
        from domain.hrowth_journey.hub.services.roadmap_generation_service import (
            RoadmapGenerationService,
        )

        async with AsyncSessionLocal() as db:
            result = await RoadmapGenerationService(db).start_run(user_id, trigger="coach")
        if result.get("already_running"):
            return {"already_running": True, "message": "이미 로드맵 생성이 진행 중입니다."}
        return {"started": True, "message": "로드맵 생성을 시작했습니다. 로드맵 탭에서 진행 상황을 볼 수 있습니다."}

    return [launch_roadmap_generation]
