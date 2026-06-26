# Gold — 사용자 프로필(관심·직무) × 활성 공고를 키워드·섹터 기반으로 매칭하는 서비스

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.market_insight.hub.repositories.chance_repository import ChanceRepository


# 공고×사용자 코사인 → 0~100 매핑 전역 고정 앵커(휴리스틱, 실데이터로 튜닝).
CHANCE_COS_LO = 0.10
CHANCE_COS_HI = 0.60


def scale_cosine(cosine: float) -> float:
    """원시 코사인을 전역 고정 기준으로 0~100 절대 스케일. 순수 함수."""
    span = CHANCE_COS_HI - CHANCE_COS_LO
    if span <= 0:
        return 50.0
    return max(0.0, min(100.0, (cosine - CHANCE_COS_LO) / span * 100.0))


def _sector_hit(opp_sector: str | None, user_keywords: list[str]) -> bool:
    if not opp_sector:
        return False
    return any(
        opp_sector.replace("-", " ") in k.lower() or opp_sector in k.lower()
        for k in user_keywords
        if isinstance(k, str)
    )


def semantic_match_score(
    cosine: float, user_terms: list[str], opp_text: str, opp_sector: str | None,
    user_keywords: list[str],
) -> tuple[int, str]:
    """임베딩 코사인을 1차 신호로, 키워드·섹터 일치를 보조 가산으로 0~100 점수·사유 산출.

    순수 함수(무네트워크·무DB) — 단위 테스트 대상. 결정론적.
    """
    base = scale_cosine(cosine)
    text = (opp_text or "").lower()
    terms = [t.strip() for t in user_terms if isinstance(t, str) and t.strip()]
    matched = [t for t in terms if t.lower() in text]
    bonus = min(15, len(matched) * 5) + (10 if _sector_hit(opp_sector, user_keywords) else 0)
    reason = f"의미 유사도 {round(base)}점"
    if matched:
        reason += " · 키워드: " + ", ".join(dict.fromkeys(matched))
    score = int(max(0, min(100, round(base + bonus))))
    return score, reason[:255]


def score_match(user_terms: list[str], opp_text: str, opp_sector: str | None,
                user_keywords: list[str]) -> tuple[int, str]:
    """임베딩이 없는 (user·opp) 폴백 — 키워드·섹터 일치 기반. 순수 함수.

    의미 매칭(semantic_match_score)이 불가할 때만 사용된다.
    """
    text = (opp_text or "").lower()
    terms = [t.strip() for t in user_terms if isinstance(t, str) and t.strip()]
    matched = [t for t in terms if t.lower() in text]
    score = 25  # 직접 일치 없음 기본선
    reason = "키워드 폴백(임베딩 없음)"
    if matched:
        score = min(100, 40 + len(matched) * 20)
        reason = "키워드 폴백 일치: " + ", ".join(dict.fromkeys(matched))[:200]
    if _sector_hit(opp_sector, user_keywords):
        score = min(100, score + 15)
    return score, reason[:255]


class ChanceMatchService:
    """프로필 보유 사용자 × 활성 공고 적합도를 재계산해 user_chance_matches 멱등 적재."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ChanceRepository(session)

    async def match_all(self) -> dict:
        """모든 (프로필 사용자 × 활성 공고) 매칭 점수를 재계산한다. 멱등 upsert.

        임베딩이 있는 (사용자×공고)는 코사인 의미 매칭, 없으면 키워드 폴백.
        반환: {"users", "opportunities", "matches", "semantic", "fallback"}.
        """
        opps = await self.repo.fetch_active_opps()
        users = await self.repo.fetch_users()
        aff_rows = await self.repo.fetch_match_affinities()
        # (user_id, opp_id) → 코사인. 타입 불일치 방지 위해 키를 문자열·정수로 정규화.
        aff = {(str(r.user_id), int(r.opportunity_id)): float(r.cosine) for r in aff_rows}

        matches = 0
        semantic = 0
        fallback = 0
        for u in users:
            keywords = u.interest_keywords if isinstance(u.interest_keywords, list) else []
            user_terms = list(keywords) + ([u.target_job] if u.target_job else [])
            for o in opps:
                opp_text = " ".join(
                    str(x) for x in (o.title, o.opportunity_type, o.benefit_summary, o.target_audience) if x
                )
                cosine = aff.get((str(u.user_id), int(o.id)))
                if cosine is not None:
                    score, reason = semantic_match_score(
                        cosine, user_terms, opp_text, o.sector_slug, keywords
                    )
                    semantic += 1
                elif user_terms:
                    # 임베딩 미보유(사용자 또는 공고) → 키워드 폴백.
                    score, reason = score_match(user_terms, opp_text, o.sector_slug, keywords)
                    fallback += 1
                else:
                    # 임베딩도 키워드도 없으면 매칭 근거 없음 — 건너뜀.
                    continue
                await self.repo.upsert_match(u.user_id, o.id, score, reason)
                matches += 1
        await self.session.commit()
        return {
            "users": len(users),
            "opportunities": len(opps),
            "matches": matches,
            "semantic": semantic,
            "fallback": fallback,
        }
