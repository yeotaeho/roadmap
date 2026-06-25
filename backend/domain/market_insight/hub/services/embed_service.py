# Silver/RAG — Gap·Chance·신호 소스와 사용자 프로필을 임베딩해 적재하는 서비스

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.embed_repository import EmbedRepository

DEFAULT_LIMIT = 300
_BATCH = 64
MAX_INPUT_CHARS = 1000


class DocumentEmbedService:
    """미임베딩 소스 텍스트(gap·chance·신호)를 임베딩해 document_embeddings에 적재(멱등)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = EmbedRepository(session)
        settings = get_settings()
        self._model = settings.llm_embed_model
        self._llm = LlmClient(
            api_key=settings.openai_api_key,
            model=settings.llm_classify_model,
            embed_model=self._model,
        )

    async def embed_documents(self, limit: int = DEFAULT_LIMIT) -> dict:
        rows = await self.repo.fetch_unembedded_docs(self._model, limit)
        embedded = 0
        for i in range(0, len(rows), _BATCH):
            chunk = rows[i : i + _BATCH]
            texts = [(r.content or "").strip()[:MAX_INPUT_CHARS] or "_" for r in chunk]
            vectors = await self._llm.embed(texts)
            for r, vec in zip(chunk, vectors):
                await self.repo.insert_doc_embedding(
                    r.source_table, r.source_id, (r.content or "")[:MAX_INPUT_CHARS],
                    vec, self._model, r.sector_slug,
                )
                embedded += 1
        await self.session.commit()
        return {"scanned": len(rows), "embedded": embedded}


class UserEmbedService:
    """미임베딩 사용자 프로필(직무·관심)을 임베딩해 user_embeddings에 적재(멱등)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = EmbedRepository(session)
        settings = get_settings()
        self._model = settings.llm_embed_model
        self._llm = LlmClient(
            api_key=settings.openai_api_key,
            model=settings.llm_classify_model,
            embed_model=self._model,
        )

    @staticmethod
    def _user_text(target_job, interest_keywords) -> str:
        kws = interest_keywords if isinstance(interest_keywords, list) else []
        parts = ([target_job] if target_job else []) + [str(k) for k in kws]
        return " ".join(parts).strip() or "_"

    async def embed_users(self, limit: int = DEFAULT_LIMIT) -> dict:
        rows = await self.repo.fetch_unembedded_users(self._model, limit)
        embedded = 0
        for i in range(0, len(rows), _BATCH):
            chunk = rows[i : i + _BATCH]
            texts = [self._user_text(r.target_job, r.interest_keywords) for r in chunk]
            vectors = await self._llm.embed(texts)
            for r, vec, t in zip(chunk, vectors, texts):
                version = hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]
                await self.repo.upsert_user_embedding(r.user_id, vec, version, self._model)
                embedded += 1
        await self.session.commit()
        return {"scanned": len(rows), "embedded": embedded}
