# 로드맵 플래너 — 페르소나·목표·관심사로 개인화 로드맵 생성(LLM, 폴백 템플릿) → 저장

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.hrowth_journey.hub.repositories.roadmap_repository import RoadmapRepository


def build_planner_context(
    persona: dict,
    target_job: str | None,
    keywords: list[str],
    movers: list[dict] | None = None,
    gaps: list[dict] | None = None,
) -> str:
    """LLM 입력 맥락 문자열 조립. 무네트워크 순수 함수.

    페르소나·목표·관심사에 더해 시장 트렌드(Pulse movers)·미해결 기회(Gap)를 주입한다.
    """
    skills = persona.get("skills") or []
    exps = persona.get("experiences") or []
    edus = persona.get("education") or []
    parts = [f"[목표 직무] {target_job or '미정'}"]
    parts.append(f"[관심 키워드] {', '.join(keywords) if keywords else '없음'}")
    parts.append("[보유 스킬]")
    parts += [f"- {s.get('name')} ({s.get('level', '입문')})" for s in skills] or ["- (없음)"]
    parts.append("[경험]")
    parts += [
        f"- {e.get('title')}: {e.get('description', '')} ({e.get('period', '')})" for e in exps
    ] or ["- (없음)"]
    parts.append("[학력]")
    parts += [
        f"- {e.get('school')} {e.get('major', '')} {e.get('degree', '')} ({e.get('status', '')})"
        for e in edus
    ] or ["- (없음)"]
    if persona.get("summary"):
        parts.append(f"[요약] {persona['summary']}")
    if movers:
        parts.append("[시장 트렌드 상위 — Pulse]")
        parts += [
            f"- {m.get('sector_slug')}: 점수 {m.get('score')}"
            + (f", 모멘텀 {m.get('momentum_pct')}%" if m.get("momentum_pct") is not None else "")
            for m in movers
        ]
    if gaps:
        parts.append("[미해결 기회 신호 — Gap]")
        parts += [f"- {g.get('problem')} → {g.get('chance')}" for g in gaps]
    return "\n".join(parts)


def template_roadmap(persona: dict, target_job: str | None, keywords: list[str]) -> dict:
    """LLM 미사용/실패 시 결정론 폴백 로드맵. 항상 유효 스키마(루트 1개)를 보장한다."""
    skills = [s.get("name") for s in (persona.get("skills") or []) if s.get("name")]
    job = (target_job or "나의").strip()
    bridge = (keywords or skills or ["역량 탐색", "실전 경험", "포트폴리오"])[:5]
    pillars = [
        {"id": "pillar-foundation", "label": "기초 역량", "blurb": "직무 핵심 개념·도구를 손에 익힙니다."},
        {"id": "pillar-practice", "label": "실전 경험", "blurb": "작은 프로젝트로 '움직이는 증거'를 만듭니다."},
        {"id": "pillar-story", "label": "포트폴리오 스토리", "blurb": "문제-실행-성과를 한 호흡으로 정리합니다."},
    ]
    quests = [
        {"quest_key": "root", "parent_key": None, "title": "나의 시작점",
         "purpose": "프로필·관심사에서 도출된 지금 위치입니다.", "difficulty": "입문",
         "keywords": bridge[:2], "state": "start", "sort_order": 0},
        {"quest_key": "q-foundation", "parent_key": "root", "title": f"{job} 기초 다지기",
         "purpose": "목표 직무의 핵심 개념·도구를 정리해 언어를 익힙니다.", "difficulty": "입문",
         "keywords": bridge[:3], "state": "available", "sort_order": 0},
        {"quest_key": "q-project", "parent_key": "root", "title": "도메인 미니 프로젝트",
         "purpose": "실제 문제 하나를 정의하고 코드·문서로 해결의 궤적을 남깁니다.", "difficulty": "중급",
         "keywords": bridge[:3], "state": "available", "sort_order": 1},
        {"quest_key": "q-portfolio", "parent_key": "q-project", "title": "포트폴리오·피치 정리",
         "purpose": "문제-실행-성과를 3분 피치로 구조화합니다.", "difficulty": "중급",
         "keywords": ["STAR", "임팩트", "피치"], "state": "locked", "sort_order": 0},
    ]
    return {
        "title": f"{job} 성장 로드맵",
        "summary": "방향만 고정, 마감은 강제하지 않습니다.",
        "skill_pillars": pillars,
        "bridge_keywords": bridge,
        "quests": quests,
    }


class RoadmapPlannerService:
    """페르소나·목표·관심사 → 개인화 로드맵 생성·저장."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RoadmapRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._api_key = settings.openai_api_key

    async def generate_for_user(self, user_id: str) -> dict:
        """호출 사용자의 로드맵 재생성. 반환: {generated, source, quest_count, roadmap_id}."""
        persona = await self.repo.fetch_persona(user_id)
        sync = await self.repo.fetch_sync_profile(user_id)
        target_job = sync["target_job"]
        keywords = sync["interest_keywords"]
        movers = await self.repo.fetch_top_movers()
        gaps = await self.repo.fetch_recent_gaps()

        roadmap: dict = {}
        source = "template"
        if self._api_key:
            try:
                llm = LlmClient(api_key=self._api_key, model=self._model)
                roadmap = await llm.generate_roadmap(
                    build_planner_context(persona, target_job, keywords, movers, gaps)
                )
                if roadmap:
                    source = "llm"
            except Exception:
                roadmap = {}
        if not roadmap:
            roadmap = template_roadmap(persona, target_job, keywords)
            source = "template"

        rid = await self.repo.save_roadmap(user_id, roadmap)
        return {
            "generated": len(roadmap.get("quests") or []),
            "source": source,
            "quest_count": len(roadmap.get("quests") or []),
            "roadmap_id": rid,
        }
