# Gold — 당일 경제 신호를 청년 진로 관점 3줄 브리핑으로 생성·서빙하는 서비스

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.briefing_repository import BriefingRepository

PROMPT_VERSION = "v1"
ECON_LIMIT = 12
GAP_LIMIT = 5


def _icon_for(momentum_pct: float | None) -> str:
    """모멘텀 부호로 trend_icon 결정."""
    if momentum_pct is None:
        return "WAVE"
    if momentum_pct > 5:
        return "UP_RIGHT"
    if momentum_pct < -5:
        return "DOWN_RIGHT"
    return "WAVE"


def template_briefing(movers: list[dict]) -> list[dict]:
    """LLM 폴백 — top movers로 결정론 3줄 생성(항상 3줄). 무네트워크 순수 함수."""
    lines: list[dict] = []
    for m in movers[:3]:
        mp = m.get("momentum_pct")
        delta = "" if mp is None else f" {'+' if mp >= 0 else ''}{round(mp)}%"
        content = f"{m.get('sector_name', '주요 섹터')} 트렌드{delta} — 관련 직무를 주목하세요."
        lines.append({"content": content[:255], "trend_icon": _icon_for(mp)})
    while len(lines) < 3:
        lines.append({"content": "데이터 누적 중 — 섹터 추세를 관찰하고 있습니다.", "trend_icon": "WAVE"})
    return lines[:3]


def build_context(econ: list[dict], movers: list[dict], gaps: list[dict]) -> str:
    """LLM 입력 맥락 문자열 조립. 무네트워크 순수 함수."""
    parts = ["[당일 경제 헤드라인]"]
    parts += [f"- {e.get('title', '')}" for e in econ[:ECON_LIMIT]] or ["- (없음)"]
    parts.append("\n[섹터 모멘텀 상위]")
    parts += [
        f"- {m.get('sector_name')}: {m.get('momentum_pct')}%" for m in movers[:5]
    ] or ["- (없음)"]
    parts.append("\n[최근 기회 신호]")
    parts += [f"- {g.get('chance_summary', '')}" for g in gaps[:GAP_LIMIT]] or ["- (없음)"]
    return "\n".join(parts)


class BriefingRefineService:
    """당일 경제 신호 → 3줄 브리핑 생성(LLM, 폴백 템플릿) → economic_briefings 적재·서빙."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BriefingRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._api_key = settings.openai_api_key

    async def refine_and_serve(self, force: bool = False) -> dict:
        """당일 3줄 브리핑 생성·적재. force 아니고 당일 존재 시 스킵. 멱등.

        반환: {"generated", "source": llm|template|skipped}.
        """
        if not force and await self.repo.today_exists():
            return {"generated": 0, "source": "skipped"}
        ctx = await self.repo.fetch_context(ECON_LIMIT, GAP_LIMIT)
        movers = ctx["movers"]
        lines: list[dict] = []
        source = "template"
        if self._api_key:
            try:
                llm = LlmClient(api_key=self._api_key, model=self._model)
                lines = await llm.generate_briefing(build_context(ctx["econ"], movers, ctx["gaps"]))
                if lines:
                    source = "llm"
            except Exception:
                lines = []
        if not lines:
            lines = template_briefing(movers)
            source = "template"
        await self.repo.upsert_gold(lines)
        await self.session.commit()
        return {"generated": len(lines), "source": source}
