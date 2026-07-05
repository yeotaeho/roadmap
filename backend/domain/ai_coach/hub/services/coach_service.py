# AI 코치 서비스 — 세션 영속·롤링 요약 + Sonnet tool-calling 에이전트 SSE 스트리밍

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.database import AsyncSessionLocal
from core.llm.client import LlmClient
from core.llm.provider import resolve_coach_llm, resolve_user_llm
from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository
from domain.ai_coach.spokes.agents.tools.internal_tools import build_internal_tools
from domain.ai_coach.spokes.agents.tools.web_tools import build_web_tools
from domain.ai_coach.spokes.infra.coach_graph import build_coach_graph
from domain.user_intelligence.hub.services import consult_context
from domain.user_intelligence.spokes.infra.consult_graph import disable_checkpointer, get_checkpointer

logger = logging.getLogger(__name__)

_WINDOW_N = 20
_THRESHOLD_T = 24

def _load_platform_context() -> str:
    """플랫폼 컨텍스트 문서 로드 — 파일 누락/읽기 실패 시 앱 부팅을 죽이지 않고 빈 문자열로 fail-open."""
    path = Path(__file__).resolve().parents[2] / "docs" / "platform_context.md"
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"플랫폼 컨텍스트 문서 로드 실패(빈 문자열로 대체): {e}")
        return ""


_PLATFORM_CONTEXT = _load_platform_context()

_COACH_SYSTEM_PROMPT = """당신은 Roadmap 플랫폼의 AI 진로 코치다. 상담실이 파악한 사용자의 성향과
플랫폼이 수집·정제한 시장 데이터를 근거로, 사용자의 진로 방향·기회·실행 방법을 함께 판단한다.

[원칙]
1. 근거 우선 — 시장·기회·적합도·성향 판단은 반드시 tool 로 실데이터를 조회한 뒤 말한다. 수치를 지어내지 않는다.
2. tool 라우팅 — 트렌드는 get_pulse_trends, 미해결 기회는 get_gap_issues, 공고는 get_chance_matches,
   적합도는 get_sync_snapshot, 사용자 성향은 get_user_profile. 이 도구들로 답이 안 나오는 개방형 질문만
   search_insights(의미 검색)를 쓴다. 내부 데이터로 답할 수 없는 최신 정보(뉴스·시세·마감 임박 공고·
   기술 동향)는 web_search 로 검색하고, 찾은 페이지의 원문 확인이 필요하면 fetch_url 로 읽는다.
   내부 tool 로 충분한 질문에 웹을 쓰지 않는다.
3. 개인화 — 첫 판단 전에 get_user_profile 로 성향·근거를 확인하고, 조언을 그 사람에게 맞춘다.
   성향이 비어 있으면 상담실(/consult)에서 자기이해 대화를 먼저 하도록 권한다.
4. 인용 — 데이터를 근거로 쓸 때 어느 탭·데이터인지 자연스럽게 밝힌다(예: "Pulse 기준 AI 섹터가…").
   웹에서 가져온 정보는 반드시 출처 URL 을 함께 표기한다.
5. 역할 경계 — 성향을 새로 캐묻는 심층 조사는 상담실 몫이다. 코치는 파악된 성향을 활용해 방향·실행을 다룬다.
6. 대화 태도 — 한 턴에 핵심 하나. 단정 대신 근거와 함께 제안하고, 다음 행동을 구체적으로 제시한다.
"""


def _sse(obj: dict) -> str:
    """SSE 이벤트 1건(JSON data) 직렬화."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


class CoachService:
    def __init__(self, session: AsyncSession):
        self.session = session
        settings = get_settings()
        try:
            self._anthropic_key, self._coach_model = resolve_coach_llm(settings)
            self._llm_error = None
        except Exception as e:  # 설정 오류는 stream 에서 노출(비-LLM 엔드포인트는 유지).
            self._anthropic_key = self._coach_model = None
            self._llm_error = str(e)
        try:  # 롤링 요약은 저렴한 기존 사용자 LLM(Gemini) 재사용.
            self._sum_key, self._sum_model, self._sum_base = resolve_user_llm(settings)
        except Exception:
            self._sum_key = self._sum_model = self._sum_base = None
        self._summarizer = self._default_summarizer
        self._graph = None

    # ---- 주입점 (테스트 대체 가능) ----

    def _chat_model(self):
        from langchain_anthropic import ChatAnthropic

        # thinking 미지정 시 Sonnet 5는 adaptive thinking이 기본 활성화된다(4.6까지는 꺼져 있었음).
        # display 기본값 "omitted"로 thinking 텍스트가 항상 빈 문자열이 되고, tool 라운드 재전송 시
        # 그 블록이 불완전한 형태로 나가 "content.0.thinking.thinking: Field required" 400 을 유발한다.
        # 코치는 확장 사고가 필요 없으므로(순수 tool-calling) 명시적으로 비활성화한다.
        return ChatAnthropic(
            model=self._coach_model,
            api_key=self._anthropic_key,
            max_tokens=2048,
            thinking={"type": "disabled"},
        )

    def _build_tools(self, user_id: str) -> list:
        return build_internal_tools(user_id) + build_web_tools()

    async def _default_summarizer(self, prior_summary, older):
        if not self._sum_key:
            return prior_summary
        llm = LlmClient(api_key=self._sum_key, model=self._sum_model, base_url=self._sum_base)
        return await llm.summarize_conversation(prior_summary, older)

    # ---- 세션 수명주기 (consult 와 동일 시맨틱) ----

    async def get_or_create_session(self, user_id: str) -> str:
        repo = CoachSessionRepository(self.session)
        existing = await repo.get_latest_active_session(user_id)
        return existing or await repo.create_session(user_id)

    async def verify_owner(self, user_id: str, session_id: str) -> str:
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

    # ---- 그래프 노드 지원 ----

    async def _maybe_summarize(self, session_id: str) -> str | None:
        """새로 밀려난(아직 미요약) 오래된 메시지만 증분 롤링 요약. 독립 세션."""
        async with AsyncSessionLocal() as db:
            repo = CoachSessionRepository(db)
            sess = await repo.get_session(session_id)
            if sess is None:
                return None
            prior = sess["context_summary"]
            summarized_until = sess["summarized_until"]
            total = await repo.count_messages(session_id)
            if total <= _THRESHOLD_T:
                return prior
            cutoff = total - _WINDOW_N
            if cutoff <= summarized_until:
                return prior
            msgs = await repo.fetch_messages(session_id)
            new_older = msgs[summarized_until:cutoff]
            if not new_older:
                return prior
            try:
                summary = await self._summarizer(prior, new_older)
            except Exception as e:  # 요약 실패는 치명적이지 않음 — 기존 요약 유지.
                logger.warning(f"코치 롤링 요약 실패(기존 요약 유지): {e}")
                return prior
            if summary:
                await repo.update_summary(session_id, summary, cutoff)
                return summary
            return prior

    async def _load_history(self, session_id: str) -> list[dict]:
        """최근 윈도우 히스토리 — 방금 저장된 현재 user 메시지는 제외(별도 주입)."""
        async with AsyncSessionLocal() as db:
            all_msgs = await CoachSessionRepository(db).fetch_messages(session_id)
        history = all_msgs[:-1] if all_msgs and all_msgs[-1]["role"] == "user" else all_msgs
        _older, recent = consult_context.split_history(history, _WINDOW_N)
        return recent

    async def _load_context_system(self, user_id: str) -> str:
        """코치 시스템 프롬프트 + 플랫폼 컨텍스트. 자기모델은 tool(get_user_profile)로 조회한다."""
        return _COACH_SYSTEM_PROMPT + "\n\n" + _PLATFORM_CONTEXT

    async def _persist_assistant(self, session_id: str, content: str) -> None:
        async with AsyncSessionLocal() as db:
            await CoachSessionRepository(db).add_message(session_id, "assistant", content)

    async def _persist_assistant_if_missing(self, session_id: str, content: str) -> None:
        """강등 경로 저장 — persist 노드가 이미 같은 내용을 저장했으면 건너뛴다(이중 저장 방지)."""
        if not content:
            return
        try:
            async with AsyncSessionLocal() as db:
                msgs = await CoachSessionRepository(db).fetch_messages(session_id)
            if msgs and msgs[-1]["role"] == "assistant" and msgs[-1]["content"] == content:
                return
            await self._persist_assistant(session_id, content)
        except Exception as pe:
            logger.warning(f"코치 강등 경로 부분 응답 저장 실패: {pe}")

    async def _get_graph(self):
        if self._graph is None:
            self._graph = build_coach_graph(self, await get_checkpointer())
        return self._graph

    # ---- SSE ----

    async def stream_sse(self, user_id: str, session_id: str, message: str):
        """사용자 메시지 저장 → 코치 그래프 구동 → custom 이벤트를 SSE 로 중계."""
        async with AsyncSessionLocal() as db:
            await CoachSessionRepository(db).add_message(session_id, "user", message)

        if self._llm_error:
            yield _sse({"type": "error", "message": f"코치 모델 설정 오류 — {self._llm_error}"})
            yield _sse({"type": "done"})
            return

        graph = await self._get_graph()
        config = {"configurable": {"thread_id": session_id}}
        state_in = {"user_id": user_id, "session_id": session_id, "message": message}
        acc = ""
        try:
            async for chunk in graph.astream(state_in, config, stream_mode="custom"):
                if chunk.get("type") == "delta":
                    acc += chunk.get("content") or ""
                yield _sse(chunk)
        except Exception as e:
            # LLM·tool 오류는 agent 노드 내부에서 error 이벤트로 처리되고 여기는
            # 인프라(체크포인터·prepare/persist) 실패 전용 안전망이다.
            # 그래프 실행 실패 — 체크포인터 강등하고 부분 응답 보존.
            logger.warning(f"코치 그래프 실행 실패(체크포인터 비활성 강등): {e}")
            disable_checkpointer()
            self._graph = None
            await self._persist_assistant_if_missing(session_id, acc)
            yield _sse({"type": "error", "message": str(e)})
        yield _sse({"type": "done"})
