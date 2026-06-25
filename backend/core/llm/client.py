# 공용 LLM 클라이언트 — 비정형 텍스트를 섹터로 분류하는 얇은 OpenAI 래퍼

from __future__ import annotations

import json

_SYSTEM_PROMPT = (
    "너는 한국어 산업·투자 텍스트를 섹터로 분류하는 분류기다. "
    "주어진 텍스트를 아래 섹터 슬러그 중 가장 적합한 하나로 분류하라. "
    "어느 섹터에도 명확히 속하지 않으면 sector_slug 를 null 로 두라(억지 매핑 금지). "
    'JSON 객체만 출력하라. 형식: {"sector_slug": <슬러그 또는 null>, "confidence": <0~1 실수>}.'
)

_EXTRACT_SYSTEM_PROMPT = (
    "너는 한국어 산업·투자·담론 텍스트에서 핵심 신호를 추출하는 분석기다. "
    "텍스트의 핵심 토픽(기술·테마·이슈)을 짧은 한국어 명사구로 요약하고, 관련 핵심 키워드 3~7개를 뽑아라. "
    "토픽이 불명확하면 signal_topic 을 null 로 두라. "
    'JSON 객체만 출력하라. 형식: {"signal_topic": <명사구 또는 null>, '
    '"extracted_keywords": [<키워드>...], "confidence": <0~1 실수>}.'
)

_GAP_SYSTEM_PROMPT = (
    "너는 한국어 뉴스·보도자료에서 '세상의 미해결 문제'와 그에서 파생되는 '청년의 기회'를 찾는 분석기다. "
    "기사에 사회·산업의 구체적 미해결 문제와 청년이 잡을 수 있는 기회가 함께 드러나면 추출하라. "
    "단순 홍보·실적·인사 기사처럼 문제·기회 구조가 없으면 problem 을 null 로 두라(억지 생성 금지). "
    "problem·opportunity 는 각각 한 문장, detail 은 2~3문장, stakeholders 는 관련 주체 2~4개, "
    "next_actions 는 청년의 실행 액션 2~4개로 적어라. "
    'JSON 객체만 출력하라. 형식: {"problem": <문장 또는 null>, "opportunity": <문장 또는 null>, '
    '"detail": <문자열>, "stakeholders": [<주체>...], "next_actions": [<액션>...]}.'
)


def _parse_classification(raw: str | None, sector_list: list[str]) -> dict:
    """LLM 원시 응답(JSON 문자열)을 검증된 분류 결과로 파싱한다. 무네트워크 순수 함수.

    목록 외 슬러그·"unknown"·파싱 불가는 sector_slug=None 으로 떨군다(강제 매핑 금지).
    confidence 누락/이상치는 0.0 으로 처리하고, slug 가 None 이면 confidence 도 0.0 이다.
    """
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {"sector_slug": None, "confidence": 0.0}
    if not isinstance(obj, dict):
        return {"sector_slug": None, "confidence": 0.0}

    slug = obj.get("sector_slug")
    if not isinstance(slug, str) or slug not in sector_list:
        slug = None

    try:
        conf = float(obj.get("confidence"))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    if slug is None:
        conf = 0.0
    return {"sector_slug": slug, "confidence": conf}


def _parse_extract(raw: str | None) -> dict:
    """추출 LLM 응답을 검증된 결과로 파싱한다. 무네트워크 순수 함수.

    {signal_topic: str|None, extracted_keywords: list[str], confidence: float}.
    토픽 없거나 파싱 불가 → signal_topic=None·confidence=0.0. 키워드는 최대 10개.
    """
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        obj = {}
    if not isinstance(obj, dict):
        obj = {}

    topic = obj.get("signal_topic")
    if not isinstance(topic, str) or not topic.strip():
        topic = None

    kws = obj.get("extracted_keywords")
    if not isinstance(kws, list):
        kws = []
    kws = [str(k).strip() for k in kws if isinstance(k, (str, int, float)) and str(k).strip()][:10]

    try:
        conf = float(obj.get("confidence"))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    if topic is None:
        conf = 0.0
    return {
        "signal_topic": topic[:255] if topic else None,
        "extracted_keywords": kws,
        "confidence": conf,
    }


def _str_list(value, limit: int) -> list[str]:
    """JSON 값에서 비어있지 않은 문자열 목록을 limit 개까지 추출하는 헬퍼."""
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if isinstance(x, (str, int, float)) and str(x).strip()][:limit]


def _parse_gap(raw: str | None) -> dict:
    """Gap 추출 LLM 응답을 검증된 결과로 파싱한다. 무네트워크 순수 함수.

    problem·opportunity 둘 다 있어야 유효한 gap. 하나라도 없으면 전부 None(무귀속).
    """
    empty = {
        "problem": None, "opportunity": None, "detail": None,
        "stakeholders": [], "next_actions": [],
    }
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return empty
    if not isinstance(obj, dict):
        return empty

    problem = obj.get("problem")
    problem = problem.strip() if isinstance(problem, str) and problem.strip() else None
    opp = obj.get("opportunity")
    opp = opp.strip() if isinstance(opp, str) and opp.strip() else None
    if problem is None or opp is None:
        return empty

    detail = obj.get("detail")
    detail = detail.strip() if isinstance(detail, str) and detail.strip() else None
    return {
        "problem": problem,
        "opportunity": opp,
        "detail": detail,
        "stakeholders": _str_list(obj.get("stakeholders"), 6),
        "next_actions": _str_list(obj.get("next_actions"), 6),
    }


class LlmClient:
    """OpenAI Chat Completions 기반 분류 클라이언트. ai_coach 등 타 도메인이 재사용 가능."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        # openai 는 사용 시점에만 임포트 — 순수 파서(_parse_classification) 테스트가 의존하지 않도록.
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def classify_sector(self, text: str, sector_list: list[str]) -> dict:
        """텍스트를 단일 섹터로 분류한다. {"sector_slug": str|None, "confidence": float} 를 반환."""
        user = f"섹터 슬러그 목록: {', '.join(sector_list)}\n\n분류할 텍스트:\n{text}"
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        )
        return _parse_classification(resp.choices[0].message.content, sector_list)

    async def extract_signal(self, text: str) -> dict:
        """텍스트에서 신호 토픽·키워드를 추출한다. {signal_topic, extracted_keywords, confidence}."""
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        return _parse_extract(resp.choices[0].message.content)

    async def extract_gap(self, text: str) -> dict:
        """텍스트에서 미해결 문제·청년 기회를 추출한다. problem None 이면 gap 아님."""
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _GAP_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        return _parse_gap(resp.choices[0].message.content)
