# Gold — 사용자 프로필(관심·직무) × 활성 공고를 키워드·섹터 기반으로 매칭하는 서비스

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.market_insight.hub.repositories.chance_repository import ChanceRepository


def score_match(user_terms: list[str], opp_text: str, opp_sector: str | None,
                user_keywords: list[str]) -> tuple[int, str]:
    """사용자 관심·직무 용어와 공고 텍스트의 키워드·섹터 일치로 0~100 점수와 사유를 산출한다.

    순수 함수(무네트워크·무DB) — 단위 테스트 대상. 결정론적.
    """
    text = (opp_text or "").lower()
    terms = [t.strip() for t in user_terms if isinstance(t, str) and t.strip()]
    matched = [t for t in terms if t.lower() in text]
    score = 25  # 직접 일치 없음 기본선
    reason = "직접 키워드 일치 없음(섹터 추천)"
    if matched:
        score = min(100, 40 + len(matched) * 20)
        reason = "관심 키워드 일치: " + ", ".join(dict.fromkeys(matched))[:200]
    # 섹터가 사용자 관심 키워드에 직접 언급되면 가산.
    if opp_sector and any(opp_sector.replace("-", " ") in k.lower() or opp_sector in k.lower()
                          for k in user_keywords if isinstance(k, str)):
        score = min(100, score + 15)
    return score, reason[:255]


class ChanceMatchService:
    """프로필 보유 사용자 × 활성 공고 적합도를 재계산해 user_chance_matches 멱등 적재."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ChanceRepository(session)

    async def match_all(self) -> dict:
        """모든 (프로필 사용자 × 활성 공고) 매칭 점수를 재계산한다. 멱등 upsert.

        반환: {"users", "opportunities", "matches"}.
        """
        opps = await self.repo.fetch_active_opps()
        users = await self.repo.fetch_users()
        matches = 0
        for u in users:
            keywords = u.interest_keywords if isinstance(u.interest_keywords, list) else []
            user_terms = list(keywords) + ([u.target_job] if u.target_job else [])
            if not user_terms:
                continue
            for o in opps:
                opp_text = " ".join(
                    str(x) for x in (o.title, o.opportunity_type, o.benefit_summary, o.target_audience) if x
                )
                score, reason = score_match(user_terms, opp_text, o.sector_slug, keywords)
                await self.repo.upsert_match(u.user_id, o.id, score, reason)
                matches += 1
        await self.session.commit()
        return {"users": len(users), "opportunities": len(opps), "matches": matches}
