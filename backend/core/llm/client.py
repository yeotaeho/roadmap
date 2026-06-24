# 공용 LLM 클라이언트 — 비정형 텍스트를 섹터로 분류하는 얇은 OpenAI 래퍼

from __future__ import annotations

import json

_SYSTEM_PROMPT = (
    "너는 한국어 산업·투자 텍스트를 섹터로 분류하는 분류기다. "
    "주어진 텍스트를 아래 섹터 슬러그 중 가장 적합한 하나로 분류하라. "
    "어느 섹터에도 명확히 속하지 않으면 sector_slug 를 null 로 두라(억지 매핑 금지). "
    'JSON 객체만 출력하라. 형식: {"sector_slug": <슬러그 또는 null>, "confidence": <0~1 실수>}.'
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
