# 코치 읽기 계약(AGENT_ROADMAP §9) 단일 관문 — 정제층만 노출, 대화 원문·민감 근거 차단

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.user_intelligence.hub.repositories.consult_session_repository import ConsultSessionRepository
from domain.user_intelligence.hub.repositories.self_model_repository import SelfModelRepository
from domain.user_intelligence.hub.services.self_model_service import SelfModelService

_MAX_EVIDENCE = 8
_MAX_SUMMARIES = 3


def shape_for_coach(model: dict | None, evidence: list[dict], summaries: list[str]) -> dict:
    """자기모델·근거·상담 요약 → 코치 주입용 축약 스냅샷. 민감 근거는 2차 차단(심층 방어)."""
    safe = [e for e in (evidence or []) if not e.get("is_sensitive")]
    safe.sort(key=lambda e: e.get("confidence") or 0, reverse=True)
    return {
        "selfModel": model,
        "evidence": [{"dimension": e.get("dimension"), "content": e.get("content")} for e in safe[:_MAX_EVIDENCE]],
        "recentConsultSummaries": list(summaries or [])[:_MAX_SUMMARIES],
    }


class ConsultMemoryService:
    """코치가 user_intelligence 를 읽는 유일한 경로 — consult_messages 원문은 여기서도 조회하지 않는다."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def read_for_coach(self, user_id: str) -> dict:
        svc = SelfModelService(self.session)
        model = await svc.get_self_model_structured(user_id)
        evidence = await SelfModelRepository(self.session).fetch_evidence(user_id, include_sensitive=False)
        summaries = await ConsultSessionRepository(self.session).fetch_recent_summaries(user_id, _MAX_SUMMARIES)
        return shape_for_coach(model, evidence, summaries)
