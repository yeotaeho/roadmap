# 임베딩 리포지토리 — 미임베딩 소스/사용자 조회, document_embeddings·user_embeddings 적재

from __future__ import annotations

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import UUID

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

# 임베딩 후보 — users 기준. 프로필이 없어도 임베딩 가능 신호(비어있지 않은 자기모델 축·긍정 근거)가
# 있으면 후보(코치-only 포함). dislike-only·빈 자기모델 사용자는 임베딩할 것이 없어 자격에서 제외 —
# 매 실행 '_' 스킵으로 LIMIT 슬롯을 소모하며 유효 사용자를 밀어내지 않게 한다.
# 타임스탬프 비교에 자기모델 갱신·근거 추가를 포함해 코치 대화가 재임베딩을 트리거한다.
# ev 워터마크는 임베딩·설명 프롬프트에 입력되는 근거 전체(dislike 포함, constraint·민감 제외)를 본다 —
# dislike 변경도 설명 무효화를 트리거해야 하며, 해시 불변 후보는 touch 로 computed_at 을 전진시켜
# 영구 재후보를 막는다(embed_service 참고).
_FETCH_UNEMBEDDED_USERS = text(
    """
    SELECT u.id AS user_id, p.target_job, p.interest_keywords,
           pref.work_style, pref.company_size_pref, pref.work_type_pref, pref.work_values,
           per.skills, per.certifications, per.languages, per.projects,
           sm.riasec, sm.narrative_summary,
           e.source_version
    FROM users u
    LEFT JOIN user_sync_profiles p ON p.user_id = u.id
    LEFT JOIN user_preferences pref ON pref.user_id = u.id
    LEFT JOIN user_personas per ON per.user_id = u.id
    LEFT JOIN user_self_model sm ON sm.user_id = u.id
    LEFT JOIN (
        SELECT user_id, max(created_at) AS last_evidence_at
        FROM user_self_model_evidence
        WHERE is_sensitive = false
          AND dimension IN ('like', 'dislike', 'value', 'aspiration', 'skill_signal')
        GROUP BY user_id
    ) ev ON ev.user_id = u.id
    LEFT JOIN user_embeddings e ON e.user_id = u.id AND e.embedding_model = :model
    WHERE (
        p.user_id IS NOT NULL
        OR (sm.user_id IS NOT NULL
            AND (sm.riasec IS NOT NULL OR sm.narrative_summary IS NOT NULL))
        OR EXISTS (
            SELECT 1 FROM user_self_model_evidence pe
            WHERE pe.user_id = u.id AND pe.is_sensitive = false
              AND pe.dimension IN ('like', 'value', 'aspiration', 'skill_signal')
              AND (pe.polarity IS NULL OR pe.polarity <> 'dislike')
        )
    )
      AND (
        e.user_id IS NULL
        OR GREATEST(
             COALESCE(p.updated_at, to_timestamp(0)),
             COALESCE(pref.updated_at, to_timestamp(0)),
             COALESCE(per.updated_at, to_timestamp(0)),
             COALESCE(sm.updated_at, to_timestamp(0)),
             COALESCE(ev.last_evidence_at, to_timestamp(0))
           ) > e.computed_at
      )
    LIMIT :lim
    """
)

# 임베딩용 비민감·긍정 근거 — 사용자별 confidence·최신순 상위 N. dislike/constraint/민감 제외.
_FETCH_POSITIVE_EVIDENCE = text(
    """
    SELECT user_id, content FROM (
        SELECT user_id, content,
               ROW_NUMBER() OVER (
                   PARTITION BY user_id
                   ORDER BY confidence DESC NULLS LAST, created_at DESC, id DESC
               ) AS rn
        FROM user_self_model_evidence
        WHERE user_id IN :uids
          AND is_sensitive = false
          AND dimension IN ('like', 'value', 'aspiration', 'skill_signal')
          AND (polarity IS NULL OR polarity <> 'dislike')
    ) t
    WHERE rn <= :per_user
    ORDER BY user_id, rn
    """
).bindparams(bindparam("uids", expanding=True, type_=UUID(as_uuid=False)))

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


# 사용자 임베딩이 실제로 갱신된 순간 = 개인화 컨텍스트가 실질 변경된 순간 —
# 점수·사유가 우연히 불변이어도 낡은 개인화 설명이 남지 않도록 해당 사용자의 매치 설명을 무효화.
_CLEAR_USER_MATCH_EXPLANATIONS = text(
    """
    UPDATE user_chance_matches
    SET match_explanation = NULL
    WHERE user_id = CAST(:user_id AS UUID) AND match_explanation IS NOT NULL
    """
)

# 동일 취지의 Sync 대칭 — 당일 행의 설명도 컨텍스트 변경 시 무효화(내일 행은 어차피 NULL 시작).
_CLEAR_USER_SYNC_EXPLANATIONS = text(
    """
    UPDATE sync_scores_daily
    SET explanation = NULL
    WHERE user_id = CAST(:user_id AS UUID)
      AND recorded_date = CURRENT_DATE
      AND explanation IS NOT NULL
    """
)

# 해시 불변 후보의 워터마크 소진 — 임베딩 텍스트 밖 프롬프트 입력(dislike 등)만 바뀐 경우
# computed_at 을 전진시켜 다음 실행부터 후보에서 빠지게 한다(설명 무효화는 호출부에서 동반).
_TOUCH_USER_EMBEDDING = text(
    "UPDATE user_embeddings SET computed_at = now() WHERE user_id = CAST(:user_id AS UUID)"
)

# 임베딩 가능 신호가 전부 사라진 사용자의 정리 — 낡은 벡터가 의미 매칭을 계속 만들지 않게 삭제.
_DELETE_USER_EMBEDDING = text(
    "DELETE FROM user_embeddings WHERE user_id = CAST(:user_id AS UUID)"
)

# 신호 소실 사용자의 매치 잔재 삭제 — 임베딩·키워드 둘 다 없으면 재점수 불가라 서빙 근거가 없다.
_DELETE_USER_MATCHES = text(
    "DELETE FROM user_chance_matches WHERE user_id = CAST(:user_id AS UUID)"
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

    async def clear_user_match_explanations(self, user_id) -> int:
        """개인화 컨텍스트 변경(임베딩 실갱신) 사용자의 매치 설명을 무효화한다. 갱신 행 수 반환."""
        result = await self.session.execute(
            _CLEAR_USER_MATCH_EXPLANATIONS, {"user_id": str(user_id)}
        )
        return result.rowcount or 0

    async def touch_user_embedding(self, user_id) -> int:
        """해시 불변 후보의 computed_at 을 전진시켜 워터마크를 소진한다. 갱신 행 수 반환."""
        result = await self.session.execute(_TOUCH_USER_EMBEDDING, {"user_id": str(user_id)})
        return result.rowcount or 0

    async def clear_user_sync_explanations(self, user_id) -> int:
        """개인화 컨텍스트 변경 사용자의 당일 Sync 설명을 무효화한다. 갱신 행 수 반환."""
        result = await self.session.execute(
            _CLEAR_USER_SYNC_EXPLANATIONS, {"user_id": str(user_id)}
        )
        return result.rowcount or 0

    async def delete_user_embedding(self, user_id) -> int:
        """신호 소실 사용자의 임베딩을 삭제한다. 삭제 행 수 반환."""
        result = await self.session.execute(_DELETE_USER_EMBEDDING, {"user_id": str(user_id)})
        return result.rowcount or 0

    async def delete_user_matches(self, user_id) -> int:
        """신호 소실 사용자의 매치 잔재를 삭제한다. 삭제 행 수 반환."""
        result = await self.session.execute(_DELETE_USER_MATCHES, {"user_id": str(user_id)})
        return result.rowcount or 0

    async def fetch_positive_evidence(self, user_ids: list, per_user: int = 10) -> dict[str, list[str]]:
        """사용자별 임베딩용 비민감·긍정 근거 content 목록. {str(user_id): [content...]}."""
        if not user_ids:
            return {}
        rows = (
            await self.session.execute(
                _FETCH_POSITIVE_EVIDENCE,
                {"uids": [str(u) for u in user_ids], "per_user": per_user},
            )
        ).all()
        out: dict[str, list[str]] = {}
        for r in rows:
            out.setdefault(str(r.user_id), []).append(r.content)
        return out
