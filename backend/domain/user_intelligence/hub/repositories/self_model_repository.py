# 자기모델 리포지토리 — 구조 척추 upsert·근거 append(dedup)·조회(민감 격리)

from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository


def normalize_content(content: str) -> str:
    """근거 dedup 용 정규화 — 앞뒤 공백 제거·연속 공백 압축·소문자."""
    return re.sub(r"\s+", " ", (content or "").strip().lower())


def content_hash(dimension: str, polarity: str | None, content: str) -> str:
    """(dimension|polarity|정규화content) SHA-256 — 세션 간 중복 근거 방지 키."""
    basis = f"{dimension}|{polarity or ''}|{normalize_content(content)}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


_FETCH_MODEL = text(
    """
    SELECT riasec, big_five, narrative_summary, axis_confidence, source, axis_source
    FROM user_self_model WHERE user_id = CAST(:uid AS UUID)
    """
)

_WRITE_MODEL = text(
    """
    INSERT INTO user_self_model
        (user_id, riasec, big_five, narrative_summary, axis_confidence, source, axis_source, updated_at)
    VALUES (CAST(:uid AS UUID), CAST(:riasec AS JSONB), CAST(:big_five AS JSONB),
            :narrative_summary, CAST(:axis_confidence AS JSONB), :source, CAST(:axis_source AS JSONB), now())
    ON CONFLICT (user_id) DO UPDATE SET
        riasec = EXCLUDED.riasec,
        big_five = EXCLUDED.big_five,
        narrative_summary = EXCLUDED.narrative_summary,
        axis_confidence = EXCLUDED.axis_confidence,
        source = EXCLUDED.source,
        axis_source = EXCLUDED.axis_source,
        updated_at = now()
    """
)

_FETCH_EVIDENCE = text(
    """
    SELECT dimension, polarity, content, confidence, is_sensitive, source
    FROM user_self_model_evidence
    WHERE user_id = CAST(:uid AS UUID)
      AND (:include_sensitive OR is_sensitive = false)
    ORDER BY created_at DESC, id DESC
    """
)

_INSERT_EVIDENCE = text(
    """
    INSERT INTO user_self_model_evidence
        (user_id, dimension, polarity, content, confidence, is_sensitive,
         content_hash, consult_session_ref, source, created_at)
    VALUES (CAST(:uid AS UUID), :dimension, :polarity, :content, :confidence, :is_sensitive,
            :content_hash, :consult_session_ref, :source, now())
    ON CONFLICT (user_id, content_hash) DO UPDATE SET
        is_sensitive = user_self_model_evidence.is_sensitive OR EXCLUDED.is_sensitive
    RETURNING (xmax = 0) AS inserted
    """
)


class SelfModelRepository(BaseRepository):
    async def fetch_self_model(self, user_id: str) -> dict | None:
        r = (await self.session.execute(_FETCH_MODEL, {"uid": user_id})).first()
        if r is None:
            return None
        return {
            "riasec": r.riasec,
            "big_five": r.big_five,
            "narrative_summary": r.narrative_summary,
            "axis_confidence": r.axis_confidence,
            "source": r.source,
            "axis_source": r.axis_source,
        }

    async def write_self_model(
        self, user_id, riasec, big_five, narrative_summary, axis_confidence, source, axis_source=None
    ) -> None:
        await self.session.execute(
            _WRITE_MODEL,
            {
                "uid": user_id,
                "riasec": json.dumps(riasec) if riasec is not None else None,
                "big_five": json.dumps(big_five) if big_five is not None else None,
                "narrative_summary": narrative_summary,
                "axis_confidence": json.dumps(axis_confidence) if axis_confidence is not None else None,
                "source": source,
                "axis_source": json.dumps(axis_source) if axis_source is not None else None,
            },
        )
        await self.session.commit()

    async def fetch_evidence(self, user_id: str, include_sensitive: bool = False) -> list[dict]:
        rows = (
            await self.session.execute(
                _FETCH_EVIDENCE, {"uid": user_id, "include_sensitive": include_sensitive}
            )
        ).all()
        return [
            {
                "dimension": r.dimension,
                "polarity": r.polarity,
                "content": r.content,
                "confidence": float(r.confidence) if r.confidence is not None else None,
                "is_sensitive": r.is_sensitive,
                "source": r.source,
            }
            for r in rows
        ]

    async def append_evidence(self, user_id: str, items: list[dict], source: str) -> int:
        inserted = 0
        for it in items:
            dim = it["dimension"]
            pol = it.get("polarity")
            content = it["content"]
            res = await self.session.execute(
                _INSERT_EVIDENCE,
                {
                    "uid": user_id,
                    "dimension": dim,
                    "polarity": pol,
                    "content": content,
                    "confidence": it.get("confidence"),
                    "is_sensitive": bool(it.get("is_sensitive", False)),
                    "content_hash": content_hash(dim, pol, content),
                    "consult_session_ref": it.get("consult_session_ref"),
                    "source": source,
                },
            )
            row = res.first()
            inserted += 1 if (row is not None and row.inserted) else 0
        await self.session.commit()
        return inserted
