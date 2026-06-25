# 임베딩 리포지토리 — 미임베딩 소스/사용자 조회, document_embeddings·user_embeddings 적재

from __future__ import annotations

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository


def vec_literal(v: list[float]) -> str:
    """임베딩 리스트를 halfvec 캐스팅용 문자열 '[..]'로 직렬화한다."""
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


# Gap·Chance·신호 소스 중 아직 임베딩 안 된 행(섹터 대표 텍스트).
_FETCH_UNEMBEDDED_DOCS = text(
    """
    SELECT source_table, source_id, sector_slug, content FROM (
        SELECT 'gap_issues' AS source_table, g.id AS source_id, g.sector_slug AS sector_slug,
               g.problem_summary || ' ' || g.chance_summary AS content
        FROM gap_issues g
        LEFT JOIN document_embeddings e
               ON e.source_table = 'gap_issues' AND e.source_id = g.id AND e.embedding_model = :model
        WHERE e.id IS NULL
        UNION ALL
        SELECT 'chance_opportunities', o.id, o.sector_slug,
               o.title || ' ' || COALESCE(o.benefit_summary, '')
        FROM chance_opportunities o
        LEFT JOIN document_embeddings e
               ON e.source_table = 'chance_opportunities' AND e.source_id = o.id AND e.embedding_model = :model
        WHERE e.id IS NULL AND o.is_active = true
        UNION ALL
        SELECT 'refined_innovation_signal', i.id, i.sector_slug, i.signal_topic
        FROM refined_innovation_signal i
        LEFT JOIN document_embeddings e
               ON e.source_table = 'refined_innovation_signal' AND e.source_id = i.id AND e.embedding_model = :model
        WHERE e.id IS NULL
    ) u
    LIMIT :lim
    """
)

_INSERT_DOC_EMB = text(
    """
    INSERT INTO document_embeddings
        (source_table, source_id, chunk_index, content_text, embedding, embedding_model, sector_slug)
    VALUES
        (:source_table, :source_id, 0, :content, CAST(:embedding AS halfvec), :model, :sector_slug)
    ON CONFLICT (source_table, source_id, chunk_index, embedding_model) DO NOTHING
    """
)

_FETCH_UNEMBEDDED_USERS = text(
    """
    SELECT p.user_id, p.target_job, p.interest_keywords
    FROM user_sync_profiles p
    LEFT JOIN user_embeddings e ON e.user_id = p.user_id AND e.embedding_model = :model
    WHERE e.user_id IS NULL
    LIMIT :lim
    """
)

_UPSERT_USER_EMB = text(
    """
    INSERT INTO user_embeddings (user_id, embedding, source_version, embedding_model, computed_at)
    VALUES (:user_id, CAST(:embedding AS halfvec), :source_version, :model, now())
    ON CONFLICT (user_id) DO UPDATE SET
        embedding = EXCLUDED.embedding,
        source_version = EXCLUDED.source_version,
        computed_at = now()
    """
)


class EmbedRepository(BaseRepository):
    async def fetch_unembedded_docs(self, model: str, limit: int) -> list:
        return list(
            (await self.session.execute(_FETCH_UNEMBEDDED_DOCS, {"model": model, "lim": limit})).all()
        )

    async def insert_doc_embedding(
        self, source_table: str, source_id: int, content: str, embedding: list[float],
        model: str, sector_slug: str | None,
    ) -> None:
        await self.session.execute(
            _INSERT_DOC_EMB,
            {
                "source_table": source_table,
                "source_id": source_id,
                "content": content,
                "embedding": vec_literal(embedding),
                "model": model,
                "sector_slug": sector_slug,
            },
        )

    async def fetch_unembedded_users(self, model: str, limit: int) -> list:
        return list(
            (await self.session.execute(_FETCH_UNEMBEDDED_USERS, {"model": model, "lim": limit})).all()
        )

    async def upsert_user_embedding(
        self, user_id, embedding: list[float], source_version: str, model: str
    ) -> None:
        await self.session.execute(
            _UPSERT_USER_EMB,
            {
                "user_id": user_id,
                "embedding": vec_literal(embedding),
                "source_version": source_version,
                "model": model,
            },
        )
