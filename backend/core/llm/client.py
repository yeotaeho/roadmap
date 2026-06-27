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

_TECH_DEMAND_GAP_SYSTEM_PROMPT = (
    "너는 한국 정부·공공기관이 공개한 '기업 수요기술'(기업이 필요로 하나 아직 확보 못한 기술) 설명에서 "
    "'시장의 미해결 갭'과 그로부터 파생되는 '청년의 기회'를 찾는 분석기다. "
    "수요기술이 가리키는 부족한 역량을 미해결 문제(problem)로, 청년이 그 역량을 키워 잡을 수 있는 기회를 opportunity 로 추출하라. "
    "수요기술로 보기 어렵거나 의미가 불명하면 problem 을 null 로 두라(억지 생성 금지). "
    "youth_fit 은 청년 개인이 자기 손으로 그 역량을 길러 진입할 수 있는 정도를 0~1 로 매겨라. "
    "0.5 같은 중립값을 남발하지 말고, 대다수 산업 수요기술은 진입장벽이 높아 0.3 이하임을 전제로 판단하라. "
    "강제 규칙 — 설비·장비·장치·소재·부품·모듈·공정·반도체·제조 라인처럼 공장·대규모 자본·B2B 인프라가 필요한 기술은 "
    "개인이 직접 만들 수 없으므로 반드시 0.1~0.3 으로 매겨라(인접 분야를 배우면 된다는 식으로 점수를 올리지 마라). "
    "0.4~0.6 은 도메인 전문성·소규모 자본이 필요하나 개인이 협업·창업으로 진입할 여지가 실제로 있는 경우에만 쓴다. "
    "0.8~0.9 는 하드웨어 없이 개인이 학습·포트폴리오만으로 진입 가능한 소프트웨어·앱·데이터분석·디자인·서비스 기술에 쓴다. "
    "예시 — '반도체 챔버 파우더 제거 공정기술'은 0.15(공장 설비·소재 공정)다. "
    "'태양광 모듈·발전 장치 기술'은 0.2(대규모 장치·설비)다. "
    "'배터리 모듈 충방전 장치 기술'은 0.2(제조 장비·자본집약)다. "
    "'산업용 IoT 센서 데이터 통합 소프트웨어'는 0.5(개인 진입 여지는 있으나 도메인 전문성 필요)다. "
    "'생성형 AI 기반 고객 응대 서비스 개발'은 0.85(개인이 학습·포트폴리오로 진입 가능)다. "
    "problem·opportunity 는 각각 한 문장, detail 은 2~3문장, stakeholders 는 관련 주체 2~4개, "
    "next_actions 는 청년의 실행 액션 2~4개로 적어라. "
    'JSON 객체만 출력하라. 형식: {"problem": <문장 또는 null>, "opportunity": <문장 또는 null>, '
    '"detail": <문자열>, "stakeholders": [<주체>...], "next_actions": [<액션>...], "youth_fit": <0~1 실수>}.'
)

_CHANCE_SYSTEM_PROMPT = (
    "너는 한국어 채용·지원사업·공모전·교육 공고를 분석하는 추출기다. "
    "공고 유형(채용/인턴/부트캠프/공모전/지원사업/교육/해커톤/기타 중 하나), 지원 대상 2~4개, "
    "혜택·보상 2~4개, 자격 요건 2~4개를 뽑고, 가장 관련된 섹터 슬러그 하나를 고르라(불명확하면 null). "
    "공고가 아니면 type 을 null 로 두라. "
    'JSON 객체만 출력하라. 형식: {"sector_slug": <슬러그 또는 null>, "type": <유형 또는 null>, '
    '"target": [<대상>...], "benefits": [<혜택>...], "qualifications": [<자격>...]}.'
)

# trend_icon 닫힌 집합 — 프론트 표시 분기와 동기화.
_BRIEFING_TREND_ICONS = ("UP_RIGHT", "DOWN_RIGHT", "WAVE")

_BRIEFING_SYSTEM_PROMPT = (
    "너는 한국 청년(10대 후반~30대 초반)에게 오늘의 경제·산업 신호를 진로 관점에서 요약하는 브리핑 작가다. "
    "주어진 당일 경제 헤드라인·섹터 모멘텀·기회 정보를 바탕으로 '세상의 변화 → 청년에게 주는 의미'를 잇는 "
    "핵심 3줄을 작성하라. 각 줄은 40자 이내 한 문장, 구체적이고 과장 없이. "
    "각 줄에 trend_icon 을 UP_RIGHT(상승·기회 확대)/DOWN_RIGHT(하락·부담)/WAVE(혼조·관망) 중 하나로 붙여라. "
    'JSON 객체만 출력하라. 형식: {"lines": [{"content": <문장>, "trend_icon": <아이콘>}, ...] — 정확히 3개}.'
)

_CAUSAL_SYSTEM_PROMPT = (
    "너는 한국어 경제·산업 뉴스에서 '거시 이벤트 → 산업 영향 → 청년 기회'의 인과 사슬을 찾는 분석기다. "
    "기사에서 (1) 거시·정책 이벤트, (2) 그것이 특정 산업에 주는 영향, (3) 거기서 청년이 잡을 수 있는 기회를 "
    "각각 한 문장으로 추출하라. 셋 중 하나라도 명확하지 않으면 macro_event 를 null 로 두라(억지 생성 금지). "
    'JSON 객체만 출력하라. 형식: {"macro_event": <문장 또는 null>, "industry_impact": <문장 또는 null>, '
    '"youth_chance": <문장 또는 null>}.'
)

_INVESTMENT_SYSTEM_PROMPT = (
    "너는 한국어 스타트업·투자 뉴스에서 투자 라운드의 '금액'을 추출하는 분석기다. "
    "기사가 억원/조원/원 단위로 금액을 밝히면 그 값을 원(KRW) 단위 정수로 환산하라(예: 100억원→10000000000). "
    "외화(USD 등)만 있고 기사에 원화 환산이 없으면 amount_krw 를 null 로 두고 currency 에 통화를 적어라(환율 추정 금지). "
    "투자 단계(Seed/Pre-A/Series A 등)와 피투자 기업명도 추출하라(없으면 null). "
    "금액이 명확하지 않으면 amount_krw 를 null 로 두라(억지 추정 금지). "
    'JSON 객체만 출력하라. 형식: {"amount_krw": <정수 또는 null>, "currency": <문자열 또는 null>, '
    '"series": <문자열 또는 null>, "company": <문자열 또는 null>}.'
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


def _parse_tech_demand_gap(raw: str | None) -> dict:
    """수요기술 Gap 추출 응답을 검증된 결과로 파싱한다. 무네트워크 순수 함수.

    problem·opportunity 둘 다 있어야 유효. 하나라도 없으면 전부 None + youth_fit 0.0(무귀속).
    youth_fit 은 0~1 로 클램프, 파싱 실패 시 0.0.
    """
    empty = {
        "problem": None, "opportunity": None, "detail": None,
        "stakeholders": [], "next_actions": [], "youth_fit": 0.0,
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
    try:
        fit = float(obj.get("youth_fit"))
    except (TypeError, ValueError):
        fit = 0.0
    fit = max(0.0, min(1.0, fit))
    return {
        "problem": problem,
        "opportunity": opp,
        "detail": detail,
        "stakeholders": _str_list(obj.get("stakeholders"), 6),
        "next_actions": _str_list(obj.get("next_actions"), 6),
        "youth_fit": fit,
    }


def _parse_chance(raw: str | None, sector_list: list[str]) -> dict:
    """Chance 추출 LLM 응답을 검증된 결과로 파싱한다. 무네트워크 순수 함수.

    type 없으면 공고 아님(무귀속). sector_slug 는 목록 외면 None(강제 매핑 금지).
    """
    empty = {"sector_slug": None, "type": None, "target": [], "benefits": [], "qualifications": []}
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return empty
    if not isinstance(obj, dict):
        return empty

    typ = obj.get("type")
    typ = typ.strip() if isinstance(typ, str) and typ.strip() else None
    if typ is None:
        return empty

    slug = obj.get("sector_slug")
    if not isinstance(slug, str) or slug not in sector_list:
        slug = None
    return {
        "sector_slug": slug,
        "type": typ[:50],
        "target": _str_list(obj.get("target"), 6),
        "benefits": _str_list(obj.get("benefits"), 6),
        "qualifications": _str_list(obj.get("qualifications"), 6),
    }


def _parse_briefing(raw: str | None) -> list[dict]:
    """3줄 경제 브리핑 LLM 응답을 검증된 줄 목록으로 파싱한다. 무네트워크 순수 함수.

    정확히 3줄(content 비어있지 않음)이 아니면 [] 반환(템플릿 폴백 신호).
    trend_icon 은 닫힌 집합 외/누락 시 WAVE 로 보정, content 는 255자 컷.
    """
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(obj, dict):
        return []
    lines = obj.get("lines")
    if not isinstance(lines, list):
        return []
    out: list[dict] = []
    for item in lines:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        icon = item.get("trend_icon")
        if icon not in _BRIEFING_TREND_ICONS:
            icon = "WAVE"
        out.append({"content": content.strip()[:255], "trend_icon": icon})
        if len(out) == 3:
            break
    return out if len(out) == 3 else []


def _parse_causal(raw: str | None) -> dict:
    """인과사슬 추출 LLM 응답을 검증한다. 무네트워크 순수 함수.

    macro_event·industry_impact·youth_chance 셋 다 있어야 유효. 하나라도 없으면 전부 None.
    """
    empty = {"macro_event": None, "industry_impact": None, "youth_chance": None}
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return empty
    if not isinstance(obj, dict):
        return empty

    def _field(key: str) -> str | None:
        v = obj.get(key)
        return v.strip() if isinstance(v, str) and v.strip() else None

    macro = _field("macro_event")
    industry = _field("industry_impact")
    youth = _field("youth_chance")
    if macro is None or industry is None or youth is None:
        return empty
    return {
        "macro_event": macro[:255],
        "industry_impact": industry[:255],
        "youth_chance": youth[:255],
    }


def _parse_investment(raw: str | None) -> dict:
    """투자 금액 추출 LLM 응답을 검증한다. 무네트워크 순수 함수.

    amount_krw 가 양수가 아니면(누락·외화전용·0) 금액 신호 없음 → 전부 None(abstain).
    """
    empty = {"amount_krw": None, "currency": None, "series": None, "company": None}
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return empty
    if not isinstance(obj, dict):
        return empty
    try:
        amount = float(obj.get("amount_krw"))
    except (TypeError, ValueError):
        return empty
    if not (amount > 0):
        return empty

    def _field(key: str, limit: int) -> str | None:
        v = obj.get(key)
        return v.strip()[:limit] if isinstance(v, str) and v.strip() else None

    return {
        "amount_krw": amount,
        "currency": _field("currency", 16) or "KRW",
        "series": _field("series", 40),
        "company": _field("company", 150),
    }


class LlmClient:
    """OpenAI Chat Completions 기반 분류 클라이언트. ai_coach 등 타 도메인이 재사용 가능."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        embed_model: str = "text-embedding-3-large",
    ) -> None:
        # openai 는 사용 시점에만 임포트 — 순수 파서(_parse_classification) 테스트가 의존하지 않도록.
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._embed_model = embed_model

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

    async def extract_tech_demand_gap(self, text: str) -> dict:
        """KIAT 수요기술에서 미해결 갭·청년 기회·youth_fit 을 추출한다. problem None 이면 무귀속."""
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _TECH_DEMAND_GAP_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        return _parse_tech_demand_gap(resp.choices[0].message.content)

    async def extract_chance(self, text: str, sector_list: list[str]) -> dict:
        """공고에서 유형·대상·혜택·자격·섹터를 추출한다. type None 이면 공고 아님."""
        user = f"섹터 슬러그 목록: {', '.join(sector_list)}\n\n공고 텍스트:\n{text}"
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _CHANCE_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        )
        return _parse_chance(resp.choices[0].message.content, sector_list)

    async def generate_briefing(self, context: str) -> list[dict]:
        """경제 맥락에서 청년 진로 관점 3줄 브리핑을 생성한다. 무효/실패 시 []."""
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _BRIEFING_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
        )
        return _parse_briefing(resp.choices[0].message.content)

    async def extract_causal_chain(self, text: str) -> dict:
        """텍스트에서 거시→산업→청년기회 인과사슬을 추출한다. macro None 이면 무효."""
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _CAUSAL_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        return _parse_causal(resp.choices[0].message.content)

    async def extract_investment(self, text: str) -> dict:
        """투자 뉴스에서 금액(KRW)·통화·단계·기업을 추출한다. amount_krw None 이면 금액 신호 없음."""
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _INVESTMENT_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        return _parse_investment(resp.choices[0].message.content)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """텍스트 목록을 임베딩 벡터 목록으로 변환한다(text-embedding-3-large, 3072차원)."""
        if not texts:
            return []
        resp = await self._client.embeddings.create(model=self._embed_model, input=texts)
        return [d.embedding for d in resp.data]
