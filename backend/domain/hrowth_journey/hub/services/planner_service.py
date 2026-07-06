# 플래너 서비스 — 보드 서빙·스프린트/태스크 CRUD·AI 퀘스트 분해(폴백 템플릿)

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.hrowth_journey.hub.repositories.planner_repository import PlannerRepository


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def serialize_sprint(row: dict) -> dict:
    """DB row(snake) → API 응답(camel)."""
    return {
        "id": row["id"],
        "title": row["title"],
        "goal": row["goal"],
        "startDate": _iso(row["start_date"]),
        "endDate": _iso(row["end_date"]),
        "state": row["state"],
        "position": row["position"],
    }


def serialize_task(row: dict) -> dict:
    """DB row(snake) → API 응답(camel)."""
    return {
        "id": row["id"],
        "sprintId": row["sprint_id"],
        "questKey": row["quest_key"],
        "title": row["title"],
        "description": row["description"] or "",
        "status": row["status"],
        "startDate": _iso(row["start_date"]),
        "dueDate": _iso(row["due_date"]),
        "estimatedDays": row["estimated_days"],
        "position": row["position"],
        "source": row["source"],
    }


def template_decompose(quest: dict) -> list[dict]:
    """LLM 미사용/실패 시 결정론 폴백 — 학습→실행→정리 3단계."""
    title = (quest.get("title") or "이 퀘스트").strip() or "이 퀘스트"
    return [
        {"title": f"{title} — 개념·자료 조사", "description": "핵심 개념과 참고 자료를 목록으로 정리합니다.",
         "estimated_days": 2},
        {"title": f"{title} — 실행·산출물 만들기", "description": "작게라도 동작하는 결과물 하나를 만듭니다.",
         "estimated_days": 5},
        {"title": f"{title} — 회고·노트 정리", "description": "배운 것과 막힌 지점을 노트로 남깁니다.",
         "estimated_days": 1},
    ]


def build_decompose_context(quest: dict, target_job: str | None) -> str:
    """LLM 입력 맥락 조립. 무네트워크 순수 함수."""
    keywords = quest.get("keywords") or []
    parts = [
        f"[목표 직무] {target_job or '미정'}",
        f"[퀘스트] {quest.get('title') or ''}",
        f"[목적] {quest.get('purpose') or ''}",
        f"[난이도] {quest.get('difficulty') or '입문'}",
        f"[키워드] {', '.join(keywords) if keywords else '없음'}",
    ]
    return "\n".join(parts)


class PlannerService:
    def __init__(self, db: AsyncSession):
        self.repo = PlannerRepository(db)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._api_key = settings.openai_api_key

    async def get_board(self, user_id: str) -> dict:
        sprints = await self.repo.fetch_sprints(user_id)
        tasks = await self.repo.fetch_tasks(user_id)
        return {
            "sprints": [serialize_sprint(s) for s in sprints],
            "tasks": [serialize_task(t) for t in tasks],
        }

    async def create_sprint(
        self, user_id: str, title: str, goal: str | None,
        start_date: date, end_date: date, state: str = "planned",
    ) -> dict:
        row = await self.repo.insert_sprint(user_id, title, goal, start_date, end_date, state)
        return serialize_sprint(row)

    async def update_sprint(self, user_id: str, sprint_id: int, fields: dict) -> bool:
        return await self.repo.update_sprint(user_id, sprint_id, fields)

    async def delete_sprint(self, user_id: str, sprint_id: int) -> bool:
        # 소속 태스크는 FK ON DELETE SET NULL 로 백로그 복귀
        return await self.repo.delete_sprint(user_id, sprint_id)

    async def create_task(self, user_id: str, fields: dict) -> dict:
        row = await self.repo.insert_task(user_id, fields)
        return serialize_task(row)

    async def update_task(self, user_id: str, task_id: int, fields: dict) -> bool:
        return await self.repo.update_task(user_id, task_id, fields)

    async def delete_task(self, user_id: str, task_id: int) -> bool:
        return await self.repo.delete_task(user_id, task_id)

    async def reorder_tasks(
        self, user_id: str, sprint_id: int | None, task_ids: list[int]
    ) -> int:
        return await self.repo.reorder_tasks(user_id, sprint_id, task_ids)

    async def decompose(self, user_id: str, quest_key: str) -> dict:
        """퀘스트 → 태스크 3~6개 분해 후 백로그 insert. 반환: {source, tasks}."""
        quest = await self.repo.fetch_quest(user_id, quest_key)
        if quest is None:
            return {"source": "none", "tasks": []}

        sync = await self.repo.fetch_sync_profile(user_id)
        items: list[dict] = []
        source = "template"
        if self._api_key:
            try:
                llm = LlmClient(api_key=self._api_key, model=self._model)
                items = await llm.decompose_quest(
                    build_decompose_context(quest, sync["target_job"])
                )
                if items:
                    source = "llm"
            except Exception:
                items = []
        if not items:
            items = template_decompose(quest)
            source = "template"

        created = []
        for it in items:
            row = await self.repo.insert_task(
                user_id,
                {
                    "quest_key": quest_key,
                    "title": it["title"],
                    "description": it.get("description") or None,
                    "estimated_days": it.get("estimated_days"),
                    "source": "ai",
                },
            )
            created.append(serialize_task(row))
        return {"source": source, "tasks": created}
