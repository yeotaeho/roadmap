# Silver/RAG — Gap·Chance·신호 소스와 사용자 프로필을 임베딩해 적재하는 서비스

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.embed_repository import EmbedRepository
from domain.market_insight.hub.services.user_embed_text import (
    EMPTY_EMBED_TEXT,
    build_user_embed_text,
)

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
    def _user_text(
        target_job, interest_keywords, work_style=None, company_size_pref=None,
        work_type_pref=None, work_values=None, skills=None, certifications=None,
        languages=None, projects=None, riasec=None, narrative_summary=None,
        evidence_contents=None,
    ) -> str:
        return build_user_embed_text(
            target_job, interest_keywords, work_style, company_size_pref, work_type_pref,
            work_values, skills, certifications, languages, projects,
            riasec=riasec, narrative_summary=narrative_summary,
            evidence_contents=evidence_contents,
        )

    async def embed_users(self, limit: int = DEFAULT_LIMIT) -> dict:
        rows = await self.repo.fetch_unembedded_users(self._model, limit)
        evidence_map = await self.repo.fetch_positive_evidence([r.user_id for r in rows])
        # 텍스트·해시 산출 후, 저장된 해시와 동일하면(타임스탬프상 후보지만 내용 불변) 임베딩 생략.
        pending = []
        for r in rows:
            t = self._user_text(
                r.target_job, r.interest_keywords,
                r.work_style, r.company_size_pref, r.work_type_pref, r.work_values,
                r.skills, r.certifications, r.languages, r.projects,
                riasec=r.riasec, narrative_summary=r.narrative_summary,
                evidence_contents=evidence_map.get(str(r.user_id)),
            )
            if t == EMPTY_EMBED_TEXT:
                # 사용 가능한 긍정 신호가 전혀 없는 사용자(예: dislike 근거만) —
                # 무의미한 폴백 임베딩이 임의의 의미 매칭을 만들지 않도록 적재하지 않는다.
                continue
            version = hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]
            if version != r.source_version:
                pending.append((r.user_id, t, version))
        embedded = 0
        for i in range(0, len(pending), _BATCH):
            chunk = pending[i : i + _BATCH]
            vectors = await self._llm.embed([t for _, t, _ in chunk])
            for (uid, _t, version), vec in zip(chunk, vectors):
                await self.repo.upsert_user_embedding(uid, vec, version, self._model)
                embedded += 1
            await self.session.commit()
        return {"scanned": len(rows), "embedded": embedded}
