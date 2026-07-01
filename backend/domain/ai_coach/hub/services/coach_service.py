# AI 코치 서비스 — 세션 영속·멀티턴·롤링 요약 + 맥락 주입 LLM SSE 스트리밍

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.database import AsyncSessionLocal
from core.llm.client import _COACH_SYSTEM_PROMPT, LlmClient
from domain.ai_coach.hub.repositories.coach_repository import CoachRepository
from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository
from domain.ai_coach.hub.services import coach_context

logger = logging.getLogger(__name__)

_WINDOW_N = 20
_THRESHOLD_T = 24


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
        self.session = session
        self.repo = CoachRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._api_key = settings.openai_api_key
        # 주입점(테스트 대체 가능). 기본은 실제 LLM.
        self._streamer = self._default_streamer
        self._summarizer = self._default_summarizer

    async def _default_streamer(self, messages: list[dict]):
        llm = LlmClient(api_key=self._api_key, model=self._model)
        async for delta in llm.stream_chat(messages):
            yield delta

    async def _default_summarizer(self, prior_summary, older):
        llm = LlmClient(api_key=self._api_key, model=self._model)
        return await llm.summarize_conversation(prior_summary, older)

    async def create_session(self, user_id: str) -> str:
        return await CoachSessionRepository(self.session).create_session(user_id)

    async def verify_owner(self, user_id: str, session_id: str) -> str:
        """세션 소유·존재 검증. 반환 status. 미존재 LookupError, 타인 PermissionError."""
        sess = await CoachSessionRepository(self.session).get_session(session_id)
        if sess is None:
            raise LookupError("세션을 찾을 수 없습니다.")
        if sess["user_id"] != user_id:
            raise PermissionError("세션 접근 권한이 없습니다.")
        return sess["status"]

    async def get_messages(self, user_id: str, session_id: str) -> list[dict]:
        await self.verify_owner(user_id, session_id)
        return await CoachSessionRepository(self.session).fetch_messages(session_id)

    async def end_session(self, user_id: str, session_id: str) -> None:
        await self.verify_owner(user_id, session_id)
        await CoachSessionRepository(self.session).end_session(session_id)

    async def _maybe_summarize(self, session_id: str) -> str | None:
        """임계 초과면 오래된 메시지를 롤링 요약해 저장하고, 현재 요약을 반환한다. 독립 세션 사용."""
        async with AsyncSessionLocal() as db:
            repo = CoachSessionRepository(db)
            sess = await repo.get_session(session_id)
            prior = sess["context_summary"] if sess else None
            total = await repo.count_messages(session_id)
            if not coach_context.select_to_summarize(total, _WINDOW_N, _THRESHOLD_T):
                return prior
            msgs = await repo.fetch_messages(session_id)
            older, _recent = coach_context.split_history(msgs, _WINDOW_N)
            if not older:
                return prior
            summary = await self._summarizer(prior, older)
            if summary:
                await repo.update_summary(session_id, summary)
            return summary or prior

    async def stream_sse(self, user_id: str, session_id: str, message: str):
        """사용자 메시지 저장 → 히스토리+요약+맥락 주입 스트리밍 → 어시스턴트 응답 저장(독립 세션)."""
        # 1) 사용자 메시지 저장(독립 세션 — 스트리밍 중 요청 세션 수명 회피).
        async with AsyncSessionLocal() as db:
            await CoachSessionRepository(db).add_message(session_id, "user", message)

        # 2) 롤링 요약(임계 초과 시) + 최근 윈도우 로드.
        summary = await self._maybe_summarize(session_id)
        async with AsyncSessionLocal() as db:
            all_msgs = await CoachSessionRepository(db).fetch_messages(session_id)
        # 방금 저장한 현재 user 메시지는 message 로 별도 주입하므로 히스토리에서 제외.
        history = all_msgs[:-1] if all_msgs and all_msgs[-1]["role"] == "user" else all_msgs
        _older, recent = coach_context.split_history(history, _WINDOW_N)

        # 3) 맥락.
        try:
            async with AsyncSessionLocal() as db:
                ctx = await CoachRepository(db).fetch_context(user_id)
            context_str = build_coach_context(ctx)
        except Exception as e:  # 맥락 로드 실패 시 맥락 없이 진행하되 조용히 삼키지 않는다.
            logger.warning(f"코치 맥락 로드 실패(맥락 없이 진행): {e}")
            context_str = ""
        system_content = _COACH_SYSTEM_PROMPT + ("\n\n" + context_str if context_str else "")

        if not self._api_key:
            yield _sse({"type": "delta", "content": "현재 AI 코치가 비활성화되어 있습니다(API 키 미설정)."})
            yield _sse({"type": "done"})
            return

        messages = coach_context.build_llm_messages(system_content, summary, recent, message)

        # 4) 스트리밍 + 누적.
        acc = ""
        try:
            async for delta in self._streamer(messages):
                acc += delta
                yield _sse({"type": "delta", "content": delta})
        except Exception as e:  # 스트림 도중 실패 — 에러 이벤트로 알린다.
            yield _sse({"type": "error", "message": str(e)})

        # 5) 어시스턴트 응답 저장(내용 있으면).
        if acc:
            async with AsyncSessionLocal() as db:
                await CoachSessionRepository(db).add_message(session_id, "assistant", acc)
        yield _sse({"type": "done"})
