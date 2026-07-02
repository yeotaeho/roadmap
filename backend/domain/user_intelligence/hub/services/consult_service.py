# AI 상담 서비스 — 세션 영속·멀티턴·롤링 요약 + 맥락 주입 LLM SSE 스트리밍

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.database import AsyncSessionLocal
from core.llm.client import _CONSULT_SYSTEM_PROMPT, LlmClient
from domain.user_intelligence.hub.repositories.consult_context_repository import ConsultContextRepository
from domain.user_intelligence.hub.repositories.consult_session_repository import ConsultSessionRepository
from domain.user_intelligence.hub.services import consult_context

logger = logging.getLogger(__name__)

_WINDOW_N = 20
_THRESHOLD_T = 24


def build_consult_context(ctx: dict) -> str:
    """맥락 dict → 시스템 프롬프트에 붙일 맥락 문자열. 무네트워크 순수 함수.

    상담사 맥락은 페르소나·시장 상위 섹터만 — 로드맵·퀘스트는 코치 위임이라 주입하지 않는다.
    """
    persona = ctx.get("persona") or {}
    movers = ctx.get("movers") or []
    parts = ["[사용자 맥락]"]
    skills = [s.get("name") for s in (persona.get("skills") or []) if s.get("name")]
    parts.append(f"- 보유 스킬: {', '.join(skills) if skills else '미입력'}")
    if persona.get("summary"):
        parts.append(f"- 요약: {persona['summary']}")
    if movers:
        parts.append("- 시장 상위 섹터: " + ", ".join(m.get("sector_slug") for m in movers))
    return "\n".join(parts)


def _sse(obj: dict) -> str:
    """SSE 이벤트 1건(JSON data) 직렬화."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


class ConsultService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ConsultContextRepository(session)
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
        return await ConsultSessionRepository(self.session).create_session(user_id)

    async def get_or_create_session(self, user_id: str) -> str:
        """가장 최근 active 세션이 있으면 이어가고, 없으면 새로 만든다(방문 간 재개)."""
        repo = ConsultSessionRepository(self.session)
        existing = await repo.get_latest_active_session(user_id)
        return existing or await repo.create_session(user_id)

    async def verify_owner(self, user_id: str, session_id: str) -> str:
        """세션 소유·존재 검증. 반환 status. 미존재 LookupError, 타인 PermissionError."""
        sess = await ConsultSessionRepository(self.session).get_session(session_id)
        if sess is None:
            raise LookupError("세션을 찾을 수 없습니다.")
        if sess["user_id"] != user_id:
            raise PermissionError("세션 접근 권한이 없습니다.")
        return sess["status"]

    async def get_messages(self, user_id: str, session_id: str) -> list[dict]:
        await self.verify_owner(user_id, session_id)
        return await ConsultSessionRepository(self.session).fetch_messages(session_id)

    async def end_session(self, user_id: str, session_id: str) -> None:
        await self.verify_owner(user_id, session_id)
        await ConsultSessionRepository(self.session).end_session(session_id)

    async def _maybe_summarize(self, session_id: str) -> str | None:
        """새로 밀려난(아직 미요약) 오래된 메시지만 증분 롤링 요약. 독립 세션."""
        async with AsyncSessionLocal() as db:
            repo = ConsultSessionRepository(db)
            sess = await repo.get_session(session_id)
            if sess is None:
                return None
            prior = sess["context_summary"]
            summarized_until = sess["summarized_until"]
            total = await repo.count_messages(session_id)
            if total <= _THRESHOLD_T:
                return prior
            cutoff = total - _WINDOW_N  # messages[:cutoff] 가 오래된 것, [cutoff:] 가 최근 윈도우
            if cutoff <= summarized_until:
                return prior  # 새로 요약할 오래된 메시지 없음
            msgs = await repo.fetch_messages(session_id)
            new_older = msgs[summarized_until:cutoff]  # 아직 미요약분만
            if not new_older:
                return prior
            try:
                summary = await self._summarizer(prior, new_older)
            except Exception as e:  # 요약 실패는 치명적이지 않음 — 기존 요약 유지하고 대화는 계속.
                logger.warning(f"롤링 요약 실패(기존 요약 유지): {e}")
                return prior
            if summary:
                await repo.update_summary(session_id, summary, cutoff)
                return summary
            return prior

    async def stream_sse(self, user_id: str, session_id: str, message: str):
        """사용자 메시지 저장 → 히스토리+요약+맥락 주입 스트리밍 → 어시스턴트 응답 저장(독립 세션)."""
        # 1) 사용자 메시지 저장(독립 세션 — 스트리밍 중 요청 세션 수명 회피).
        async with AsyncSessionLocal() as db:
            await ConsultSessionRepository(db).add_message(session_id, "user", message)

        # 2) API 키 미설정 시 요약/히스토리/맥락 로드 없이 즉시 비활성 폴백.
        if not self._api_key:
            yield _sse({"type": "delta", "content": "현재 AI 상담이 비활성화되어 있습니다(API 키 미설정)."})
            yield _sse({"type": "done"})
            return

        # 3) 롤링 요약(임계 초과 시) + 최근 윈도우 로드.
        summary = await self._maybe_summarize(session_id)
        async with AsyncSessionLocal() as db:
            all_msgs = await ConsultSessionRepository(db).fetch_messages(session_id)
        # 방금 저장한 현재 user 메시지는 message 로 별도 주입하므로 히스토리에서 제외.
        history = all_msgs[:-1] if all_msgs and all_msgs[-1]["role"] == "user" else all_msgs
        _older, recent = consult_context.split_history(history, _WINDOW_N)

        # 4) 맥락.
        try:
            async with AsyncSessionLocal() as db:
                ctx = await ConsultContextRepository(db).fetch_context(user_id)
            context_str = build_consult_context(ctx)
        except Exception as e:  # 맥락 로드 실패 시 맥락 없이 진행하되 조용히 삼키지 않는다.
            logger.warning(f"상담 맥락 로드 실패(맥락 없이 진행): {e}")
            context_str = ""
        system_content = _CONSULT_SYSTEM_PROMPT + ("\n\n" + context_str if context_str else "")

        messages = consult_context.build_llm_messages(system_content, summary, recent, message)

        # 5) 스트리밍 + 누적.
        acc = ""
        try:
            async for delta in self._streamer(messages):
                acc += delta
                yield _sse({"type": "delta", "content": delta})
        except Exception as e:  # 스트림 도중 실패 — 에러 이벤트로 알린다.
            yield _sse({"type": "error", "message": str(e)})

        # 6) 어시스턴트 응답 저장(내용 있으면).
        if acc:
            async with AsyncSessionLocal() as db:
                await ConsultSessionRepository(db).add_message(session_id, "assistant", acc)
        yield _sse({"type": "done"})
