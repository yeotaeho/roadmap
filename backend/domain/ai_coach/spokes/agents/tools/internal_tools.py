# 코치 내부 조회 tool 6종 — 기존 Gold·자기모델 정제층의 read-only LangChain tool 래퍼

from __future__ import annotations

from functools import lru_cache
from langchain_core.tools import tool

from core.database import AsyncSessionLocal

TOOL_LABELS: dict[str, str] = {
    "get_pulse_trends": "시장 트렌드 조회",
    "get_gap_issues": "미해결 기회 조회",
    "get_chance_matches": "맞춤 공고 조회",
    "get_sync_snapshot": "섹터 적합도 조회",
    "get_user_profile": "사용자 성향 조회",
    "search_insights": "인사이트 의미 검색",
}


@lru_cache(maxsize=1)
def _embed_client():
    """프로세스 싱글턴 임베딩 클라이언트 — 호출마다 커넥션 풀 재생성 방지."""
    from openai import AsyncOpenAI

    from core.config.settings import get_settings

    return AsyncOpenAI(api_key=get_settings().openai_api_key)


async def _embed_query(query: str) -> list[float]:
    """쿼리 임베딩 — 저장 임베딩과 동일 모델(text-embedding-3-large) 강제."""
    from core.config.settings import get_settings

    client = _embed_client()
    res = await client.embeddings.create(model=get_settings().llm_embed_model, input=query)
    return res.data[0].embedding


def build_internal_tools(user_id: str) -> list:
    """user_id 를 클로저로 고정한 tool 목록 — LLM 인자로 user_id 를 받지 않는다(권한 상승 차단)."""
    from domain.ai_coach.hub.repositories.coach_insight_repository import CoachInsightRepository

    @tool
    async def get_pulse_trends(sector_slug: str | None = None) -> dict:
        """12개 산업 섹터의 최신 트렌드 점수·모멘텀·배지를 조회한다. sector_slug 를 주면 해당 섹터만."""
        async with AsyncSessionLocal() as db:
            return await CoachInsightRepository(db).pulse_trends(sector_slug)

    @tool
    async def get_gap_issues(sector_slug: str | None = None, issue_id: int | None = None) -> dict:
        """시장의 미해결 문제·청년 기회(Gap 이슈)를 조회한다. issue_id 를 주면 상세·실행 제안까지."""
        async with AsyncSessionLocal() as db:
            return await CoachInsightRepository(db).gap_issues(sector_slug, issue_id)

    @tool
    async def get_chance_matches(opportunity_type: str | None = None) -> dict:
        """사용자 맞춤 공고(채용 JOB·부트캠프 BOOTCAMP·공모전 CONTEST·지원사업 GRANT)와 매칭 점수를 조회한다."""
        async with AsyncSessionLocal() as db:
            return await CoachInsightRepository(db).chance_matches(user_id, opportunity_type)

    @tool
    async def get_sync_snapshot() -> dict:
        """사용자의 섹터별 최신 적합도(Sync) 점수·설명을 조회한다."""
        async with AsyncSessionLocal() as db:
            return await CoachInsightRepository(db).sync_snapshot(user_id)

    @tool
    async def get_user_profile() -> dict:
        """사용자 자기모델(RIASEC·Big Five·서사)과 비민감 근거, 최근 상담 요약을 조회한다."""
        from domain.user_intelligence.hub.services.consult_memory_service import ConsultMemoryService

        async with AsyncSessionLocal() as db:
            return await ConsultMemoryService(db).read_for_coach(user_id)

    @tool
    async def search_insights(query: str, sector_slug: str | None = None) -> dict:
        """구조화 tool 로 답이 안 나오는 개방형 질문일 때, 인사이트 문서를 의미 검색한다(최근 90일)."""
        vec = await _embed_query(query)
        async with AsyncSessionLocal() as db:
            docs = await CoachInsightRepository(db).search_documents(vec, sector_slug)
        return {"documents": docs}

    return [get_pulse_trends, get_gap_issues, get_chance_matches, get_sync_snapshot, get_user_profile, search_insights]
