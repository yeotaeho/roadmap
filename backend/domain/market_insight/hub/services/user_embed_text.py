# 사용자 임베딩/매칭용 텍스트 직렬화 - 성향·스펙 enum->한국어 라벨 (순수, 무DB·무네트워크)

from __future__ import annotations

_WORK_STYLE_LABEL = {"stability": "안정 지향", "challenge": "도전 지향", "balanced": "균형 지향"}
_COMPANY_SIZE_LABEL = {"startup": "스타트업", "sme": "중소기업", "large": "대기업", "public": "공공기관"}
_WORK_TYPE_LABEL = {"office": "사무실 근무", "remote": "원격 근무", "hybrid": "하이브리드 근무"}
_WORK_VALUE_LABEL = {
    "growth": "성장",
    "work_life_balance": "워라밸",
    "autonomy": "자율성",
    "impact": "사회적 임팩트",
    "compensation": "보상",
}

MAX_EMBED_TEXT_CHARS = 1000  # 캡 후 텍스트가 해시(source_version) 기준 — 캡으로 잘린 불변 텍스트 재임베딩 방지.
EMPTY_EMBED_TEXT = "_"  # 사용 가능한 신호가 전혀 없을 때의 폴백 — 소비자는 이 값을 임베딩하지 않아야 한다.

RIASEC_LABEL = {
    "R": "현실형",
    "I": "탐구형",
    "A": "예술형",
    "S": "사회형",
    "E": "진취형",
    "C": "관습형",
}


def _names(items, key: str) -> list[str]:
    """JSONB 리스트[{key:..}]에서 key 값 문자열만 추출(None·비dict·빈값 무시)."""
    out: list[str] = []
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                v = it.get(key)
                if v:
                    out.append(str(v))
    return out


def _tech_stack(projects) -> list[str]:
    """projects[].tech_stack 의 모든 기술 문자열을 평탄화한다."""
    out: list[str] = []
    if isinstance(projects, list):
        for p in projects:
            if isinstance(p, dict) and isinstance(p.get("tech_stack"), list):
                out.extend(str(t) for t in p["tech_stack"] if t)
    return out


def disposition_spec_terms(
    work_style=None,
    company_size_pref=None,
    work_type_pref=None,
    work_values=None,
    skills=None,
    certifications=None,
    languages=None,
    projects=None,
) -> list[str]:
    """성향·스펙을 임베딩/매칭용 한국어 용어 리스트로 변환한다. 순수·결정론."""
    terms: list[str] = []
    if work_style in _WORK_STYLE_LABEL:
        terms.append(_WORK_STYLE_LABEL[work_style])
    if company_size_pref in _COMPANY_SIZE_LABEL:
        terms.append(_COMPANY_SIZE_LABEL[company_size_pref])
    if work_type_pref in _WORK_TYPE_LABEL:
        terms.append(_WORK_TYPE_LABEL[work_type_pref])
    if isinstance(work_values, list):
        terms.extend(_WORK_VALUE_LABEL[v] for v in work_values if v in _WORK_VALUE_LABEL)
    terms += _names(skills, "name")
    terms += _names(certifications, "name")
    terms += _names(languages, "language")
    terms += _names(projects, "title")
    terms += _tech_stack(projects)
    return terms


def self_model_terms(riasec=None, narrative_summary=None, evidence_contents=None) -> list[str]:
    """자기모델(RIASEC 라벨·서사·긍정 근거)을 임베딩용 용어 리스트로 변환한다. 순수·결정론."""
    terms: list[str] = []
    codes = riasec.get("top_codes") if isinstance(riasec, dict) else None
    if isinstance(codes, list):
        terms.extend(RIASEC_LABEL[c] for c in codes if c in RIASEC_LABEL)
    if isinstance(narrative_summary, str) and narrative_summary.strip():
        terms.append(narrative_summary.strip())
    if isinstance(evidence_contents, list):
        terms.extend(str(c).strip() for c in evidence_contents if c and str(c).strip())
    return terms


def build_user_embed_text(
    target_job=None,
    interest_keywords=None,
    work_style=None,
    company_size_pref=None,
    work_type_pref=None,
    work_values=None,
    skills=None,
    certifications=None,
    languages=None,
    projects=None,
    riasec=None,
    narrative_summary=None,
    evidence_contents=None,
) -> str:
    """직무+관심키워드+성향+스펙+자기모델을 한 줄 임베딩 텍스트로 직렬화한다. 빈 입력은 '_'."""
    kws = interest_keywords if isinstance(interest_keywords, list) else []
    parts = ([target_job] if target_job else []) + [str(k) for k in kws]
    parts += disposition_spec_terms(
        work_style, company_size_pref, work_type_pref, work_values,
        skills, certifications, languages, projects,
    )
    parts += self_model_terms(riasec, narrative_summary, evidence_contents)
    text = " ".join(p for p in parts if p).strip()
    return text[:MAX_EMBED_TEXT_CHARS].strip() or EMPTY_EMBED_TEXT
