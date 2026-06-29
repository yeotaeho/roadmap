# Silver — raw_economic/discourse 자유 텍스트를 LLM으로 섹터 분류해 멱등 적재하는 서비스

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.pulse_repository import PulseRepository

# 프롬프트·파서 규칙 버전. 분류 의미가 바뀔 때만 bump(자연키에 포함되어 버전 격리).
PROMPT_VERSION = "v1"
ACTIVE_WINDOW_DAYS = 90
DEFAULT_LIMIT = 500
# 분류 입력 텍스트 상한(섹터 판별엔 제목+리드로 충분, 토큰 비용 제어).
MAX_INPUT_CHARS = 2000
# LLM 분류 중간 적재·커밋 주기. 큰 limit 에서 LLM idle 이 DB 연결 수명(pool_recycle)을
# 초과해 connection closed 되는 것을 방지한다(청크마다 연결 반환).
CLASSIFY_CHUNK = 25

# 분류 대상 raw 테이블(자유 텍스트 원천). innovation 은 KIAT·KISTEP만(fetch SQL에서 필터).
_TARGET_TABLES = ("raw_economic_data", "raw_discourse_data", "raw_innovation_data")

# sectors 시드와 동기화된 12개 섹터 슬러그(d7f3a9c1e5b2 마이그레이션 기준).
SECTOR_SLUGS = [
    "ai-data", "semiconductor", "bio-health", "energy-climate", "mobility",
    "fintech", "content-creator", "edutech", "food-agri", "social-service",
    "logistics", "beauty-fashion",
]


class TextSectorClassifyService:
    """미분류 raw 자유 텍스트를 LLM 섹터 분류 후 refined_text_sector_class 에 멱등 적재."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PulseRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._llm = LlmClient(api_key=settings.openai_api_key, model=self._model)

    async def classify_unclassified(
        self, window_days: int = ACTIVE_WINDOW_DAYS, limit: int = DEFAULT_LIMIT
    ) -> dict:
        """최근 window_days 내 미분류 행을 분류·적재한다. 멱등(자연키 충돌 무시).

        반환: {"scanned", "classified", "unknown"} — 스캔/섹터부여/무귀속 건수.
        """
        scanned = 0
        classified = 0
        unknown = 0
        for table_ref in _TARGET_TABLES:
            rows = await self.repo.fetch_unclassified_text_rows(
                table_ref, PROMPT_VERSION, window_days, limit
            )
            payload: list[dict] = []
            for raw_id, body in rows:
                scanned += 1
                input_text = (body or "").strip()[:MAX_INPUT_CHARS]
                result = await self._llm.classify_sector(input_text, SECTOR_SLUGS)
                if result["sector_slug"] is not None:
                    classified += 1
                else:
                    unknown += 1
                payload.append(
                    {
                        "raw_table_ref": table_ref,
                        "raw_id": raw_id,
                        "sector_slug": result["sector_slug"],
                        "confidence": result["confidence"],
                        "sentiment": result.get("sentiment"),
                        "sentiment_score": result.get("sentiment_score"),
                        "model_name": self._model,
                        "prompt_version": PROMPT_VERSION,
                        "input_hash": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
                    }
                )
                # 청크마다 적재·커밋해 LLM idle 구간을 제한(연결 수명 초과 방지).
                if len(payload) >= CLASSIFY_CHUNK:
                    await self.repo.upsert_text_sector_class(payload)
                    await self.session.commit()
                    payload = []
            if payload:
                await self.repo.upsert_text_sector_class(payload)
                await self.session.commit()
        return {"scanned": scanned, "classified": classified, "unknown": unknown}
