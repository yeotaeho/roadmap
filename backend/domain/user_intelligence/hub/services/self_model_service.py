# 자기모델 서비스 — 병합 규칙(user_form 우위·confidence 게이팅) + 조회 셰이핑

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.user_intelligence.hub.repositories.self_model_repository import SelfModelRepository
from domain.user_intelligence.hub.services.riasec_scoring import blend_riasec

CONFIDENCE_THRESHOLD = 0.40
SOURCE_USER_FORM = "user_form"
SOURCE_COACH = "consult_extraction"
_AXES = ("riasec", "big_five", "narrative_summary")


def _incoming_conf(incoming: dict, axis: str, source: str) -> float:
    conf = (incoming.get("axis_confidence") or {}).get(axis)
    if conf is not None:
        return float(conf)
    return 1.0 if source == SOURCE_USER_FORM else 0.0


def merge_structured(existing: dict | None, incoming: dict, source: str) -> dict:
    """구조 축 병합(순수). user_form 우위·빈 축만 coach 채움·저confidence 보류.

    existing: 기존 행 dict|None. incoming: {riasec, big_five, narrative_summary, axis_confidence}.
    반환: 저장할 최종 행 dict(riasec, big_five, narrative_summary, axis_confidence, source).
    """
    base = dict(existing or {})
    existing_source = base.get("source")
    result = {axis: base.get(axis) for axis in _AXES}
    merged_conf = dict(base.get("axis_confidence") or {})

    for axis in _AXES:
        inc = incoming.get(axis)
        if inc is None:
            continue
        if axis == "riasec" and isinstance(inc, dict) and "window_scores" in inc:
            # 점수 블렌딩 — user_form 이 아닌 대화 추출만. user_form 은 아래 일반 규칙(overwrite) 유지.
            if source != SOURCE_USER_FORM:
                # user_form 으로 명시 입력된 riasec 은 코치 추출 blend 가 잠식하지 않는다(다른 축과 동일 불변식).
                if existing_source == SOURCE_USER_FORM and base.get("riasec") is not None:
                    continue
                existing_riasec = base.get("riasec") if isinstance(base.get("riasec"), dict) else None
                blended = blend_riasec(existing_riasec, inc["window_scores"], inc["window_conf"])
                result["riasec"] = blended
                merged_conf["riasec"] = sum(inc["window_conf"].values()) / len(inc["window_conf"]) if inc["window_conf"] else 0.0
                continue
        if source == SOURCE_USER_FORM:
            result[axis] = inc  # 사용자 명시 입력 최우선
            merged_conf[axis] = 1.0
            continue
        # coach/consult extraction (비riasec-scores 축)
        if existing_source == SOURCE_USER_FORM and base.get(axis) is not None:
            continue  # user_form 우위 — 덮어쓰지 않음
        conf = _incoming_conf(incoming, axis, source)
        merged_conf[axis] = conf
        if conf < CONFIDENCE_THRESHOLD:
            continue  # 저신뢰 보류 — 값 미기록, 신뢰도만 반영
        result[axis] = inc

    result["source"] = (
        SOURCE_USER_FORM
        if source == SOURCE_USER_FORM or existing_source == SOURCE_USER_FORM
        else SOURCE_COACH
    )
    result["axis_confidence"] = merged_conf or None
    return result


class SelfModelService:
    def __init__(self, db: AsyncSession):
        self.repo = SelfModelRepository(db)

    async def get_self_model(self, user_id: str, include_sensitive: bool = False) -> dict:
        """구조 축 + 근거(기본 비민감). 없으면 null 기본값."""
        model = await self.repo.fetch_self_model(user_id)
        evidence = await self.repo.fetch_evidence(user_id, include_sensitive=include_sensitive)
        if model is None:
            return {
                "riasec": None,
                "bigFive": None,
                "narrativeSummary": None,
                "axisConfidence": None,
                "source": None,
                "evidence": evidence,
            }
        return {
            "riasec": model["riasec"],
            "bigFive": model["big_five"],
            "narrativeSummary": model["narrative_summary"],
            "axisConfidence": model["axis_confidence"],
            "source": model["source"],
            "evidence": evidence,
        }

    async def upsert_structured(self, user_id: str, incoming: dict, source: str) -> dict:
        existing = await self.repo.fetch_self_model(user_id)
        merged = merge_structured(existing, incoming, source)
        await self.repo.write_self_model(
            user_id,
            riasec=merged["riasec"],
            big_five=merged["big_five"],
            narrative_summary=merged["narrative_summary"],
            axis_confidence=merged["axis_confidence"],
            source=merged["source"],
        )
        return merged

    async def append_evidence(self, user_id: str, items: list[dict], source: str) -> int:
        return await self.repo.append_evidence(user_id, items, source)
