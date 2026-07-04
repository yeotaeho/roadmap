# 자기모델 서비스 — 병합 규칙(user_form 우위·confidence 게이팅) + 조회 셰이핑

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.user_intelligence.hub.repositories.self_model_repository import SelfModelRepository
from domain.user_intelligence.hub.services.riasec_scoring import (
    BIGFIVE_CODES,
    BIGFIVE_SHRINK_K,
    RIASEC_CODES,
    SHRINK_K,
    TOP_MIN,
    blend_big_five,
    blend_riasec,
)

CONFIDENCE_THRESHOLD = 0.40
SOURCE_USER_FORM = "user_form"
SOURCE_COACH = "consult_extraction"
_AXES = ("riasec", "big_five", "narrative_summary")

LEVEL_SCORE = {"low": 25, "mid": 50, "high": 75}


def _user_form_riasec(levels: dict) -> dict:
    """레벨(낮음/중간/높음)→점수로 사용자 확정 RIASEC 구성. top_codes 파생·완전표현 가중."""
    scores = {c: LEVEL_SCORE.get(levels.get(c), 50) for c in RIASEC_CODES}
    ranked = sorted(RIASEC_CODES, key=lambda c: scores[c], reverse=True)
    top_codes = [c for c in ranked if scores[c] > TOP_MIN][:2]
    return {"scores": scores, "raw": dict(scores),
            "weights": {c: SHRINK_K for c in RIASEC_CODES}, "top_codes": top_codes}


def _user_form_big_five(levels: dict) -> dict:
    """레벨→점수로 사용자 확정 Big Five 구성. 신경성은 정서안정성 입력→canonical N=100-안정성."""
    scores = {c: LEVEL_SCORE.get(levels.get(c), 50) for c in ("O", "C", "E", "A")}
    scores["N"] = 100 - LEVEL_SCORE.get(levels.get("stability"), 50)
    return {"scores": scores, "raw": dict(scores),
            "weights": {c: BIGFIVE_SHRINK_K for c in BIGFIVE_CODES}}


def _incoming_conf(incoming: dict, axis: str, source: str) -> float:
    conf = (incoming.get("axis_confidence") or {}).get(axis)
    if conf is not None:
        return float(conf)
    return 1.0 if source == SOURCE_USER_FORM else 0.0


def _axis_is_user_form(base: dict, axis: str) -> bool:
    """해당 축이 사용자 확정(user_form)인지 — 축별 provenance."""
    src = base.get("axis_source")
    return isinstance(src, dict) and src.get(axis) == SOURCE_USER_FORM


def merge_structured(existing: dict | None, incoming: dict, source: str) -> dict:
    """구조 축 병합(순수). user_form 우위·빈 축만 coach 채움·저confidence 보류.

    existing: 기존 행 dict|None. incoming: {riasec, big_five, narrative_summary, axis_confidence}.
    반환: 저장할 최종 행 dict(riasec, big_five, narrative_summary, axis_confidence, source, axis_source).
    """
    base = dict(existing or {})
    existing_source = base.get("source")
    result = {axis: base.get(axis) for axis in _AXES}
    merged_conf = dict(base.get("axis_confidence") or {})

    for axis in _AXES:
        inc = incoming.get(axis)
        if inc is None:
            continue
        if axis in ("riasec", "big_five") and isinstance(inc, dict) and "window_scores" in inc:
            # 점수 블렌딩 — user_form 이 아닌 대화 추출만. user_form 은 아래 일반 규칙(overwrite) 유지.
            if source != SOURCE_USER_FORM:
                # user_form 으로 명시 입력된 축은 코치 추출 blend 가 잠식하지 않는다.
                if _axis_is_user_form(base, axis):
                    continue
                existing_axis = base.get(axis) if isinstance(base.get(axis), dict) else None
                blender = blend_riasec if axis == "riasec" else blend_big_five
                result[axis] = blender(existing_axis, inc["window_scores"], inc["window_conf"])
                merged_conf[axis] = sum(inc["window_conf"].values()) / len(inc["window_conf"]) if inc["window_conf"] else 0.0
                continue
        if source == SOURCE_USER_FORM:
            result[axis] = inc  # 사용자 명시 입력 최우선
            merged_conf[axis] = 1.0
            continue
        # coach/consult extraction (비riasec-scores 축)
        if _axis_is_user_form(base, axis):
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
    result["axis_source"] = base.get("axis_source")
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
                "axisSource": None,
                "evidence": evidence,
            }
        return {
            "riasec": model["riasec"],
            "bigFive": model["big_five"],
            "narrativeSummary": model["narrative_summary"],
            "axisConfidence": model["axis_confidence"],
            "source": model["source"],
            "axisSource": model.get("axis_source"),
            "evidence": evidence,
        }

    async def get_self_model_structured(self, user_id: str) -> dict:
        """구조 척추만(근거 미조회) — 배경 기억 등 evidence 불필요 경로용. camelCase."""
        model = await self.repo.fetch_self_model(user_id)
        if model is None:
            return {"riasec": None, "bigFive": None, "narrativeSummary": None, "axisConfidence": None, "axisSource": None}
        return {
            "riasec": model["riasec"],
            "bigFive": model["big_five"],
            "narrativeSummary": model["narrative_summary"],
            "axisConfidence": model["axis_confidence"],
            "axisSource": model.get("axis_source"),
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
            axis_source=merged.get("axis_source"),
        )
        return merged

    async def append_evidence(self, user_id: str, items: list[dict], source: str) -> int:
        return await self.repo.append_evidence(user_id, items, source)

    async def apply_user_edits(self, user_id: str, edits: dict) -> dict:
        """사용자 편집을 축별로 적용한다. 축 값 설정 시 user_form 고정, 'auto' 는 코치에게 반환."""
        existing = await self.repo.fetch_self_model(user_id) or {}
        riasec = existing.get("riasec")
        big_five = existing.get("big_five")
        narrative = existing.get("narrative_summary")
        axis_source = dict(existing.get("axis_source") or {})

        r = edits.get("riasec")
        if r == "auto":
            axis_source.pop("riasec", None)
        elif isinstance(r, dict) and isinstance(r.get("levels"), dict):
            riasec = _user_form_riasec(r["levels"])
            axis_source["riasec"] = SOURCE_USER_FORM

        b = edits.get("big_five")
        if b == "auto":
            axis_source.pop("big_five", None)
        elif isinstance(b, dict) and isinstance(b.get("levels"), dict):
            big_five = _user_form_big_five(b["levels"])
            axis_source["big_five"] = SOURCE_USER_FORM

        n = edits.get("narrative")
        if n == "auto":
            axis_source.pop("narrative_summary", None)
        elif isinstance(n, str):
            narrative = n.strip()[:500] or None
            if narrative is not None:
                axis_source["narrative_summary"] = SOURCE_USER_FORM
            else:
                axis_source.pop("narrative_summary", None)

        await self.repo.write_self_model(
            user_id, riasec=riasec, big_five=big_five, narrative_summary=narrative,
            axis_confidence=existing.get("axis_confidence"),
            source=existing.get("source") or SOURCE_COACH,
            axis_source=axis_source or None,
        )
        return await self.get_self_model(user_id)
