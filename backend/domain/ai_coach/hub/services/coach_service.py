# AI 코치 서비스 — 사용자 맥락 주입 + LLM 응답 SSE 스트리밍

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import _COACH_SYSTEM_PROMPT, LlmClient
from domain.ai_coach.hub.repositories.coach_repository import CoachRepository


def build_coach_context(ctx: dict) -> str:
    """맥락 dict → 시스템 프롬프트에 붙일 맥락 문자열. 무네트워크 순수 함수."""
    persona = ctx.get("persona") or {}
    roadmap = ctx.get("roadmap")
    quests = ctx.get("quests") or []
    movers = ctx.get("movers") or []
    parts = ["[사용자 맥락]"]
    skills = [s.get("name") for s in (persona.get("skills") or []) if s.get("name")]
    parts.append(f"- 보유 스킬: {', '.join(skills) if skills else '미입력'}")
    if persona.get("summary"):
        parts.append(f"- 요약: {persona['summary']}")
    if roadmap:
        parts.append(f"- 로드맵: {roadmap.get('title')}")
    if quests:
        parts.append("- 진행 중/예정 퀘스트: " + ", ".join(q.get("title") for q in quests))
    if movers:
        parts.append("- 시장 상위 섹터: " + ", ".join(m.get("sector_slug") for m in movers))
    return "\n".join(parts)


def _sse(obj: dict) -> str:
    """SSE 이벤트 1건(JSON data) 직렬화."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


class CoachService:
    def __init__(self, session: AsyncSession):
        self.repo = CoachRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._api_key = settings.openai_api_key

    async def stream_sse(self, user_id: str, message: str):
        """사용자 맥락을 주입해 코치 응답을 SSE 이벤트(async generator)로 스트리밍한다."""
        try:
            ctx = await self.repo.fetch_context(user_id)
            context_str = build_coach_context(ctx)
        except Exception:
            context_str = ""

        if not self._api_key:
            yield _sse({"type": "delta", "content": "현재 AI 코치가 비활성화되어 있습니다(API 키 미설정)."})
            yield _sse({"type": "done"})
            return

        messages = [
            {"role": "system", "content": _COACH_SYSTEM_PROMPT + "\n\n" + context_str},
            {"role": "user", "content": message},
        ]
        try:
            llm = LlmClient(api_key=self._api_key, model=self._model)
            async for delta in llm.stream_chat(messages):
                yield _sse({"type": "delta", "content": delta})
        except Exception as e:  # 스트림 도중 실패 — 에러 이벤트로 알린다.
            yield _sse({"type": "error", "message": str(e)})
        yield _sse({"type": "done"})
