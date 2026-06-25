# Silver/RAG — 소스 텍스트 임베딩(halfvec 3072) ORM

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class DocumentEmbeddings(Base):
    __tablename__ = "document_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "source_table", "source_id", "chunk_index", "embedding_model", name="uq_doc_emb_source"
        ),
        Index("ix_doc_emb_sector", "sector_slug"),
        {"comment": "Silver/RAG — 소스 텍스트 임베딩(halfvec 3072, 섹터 대표·검색)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_table: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(HALFVEC(3072), nullable=False)
    embedding_model: Mapped[str] = mapped_column(
        String(60), server_default="text-embedding-3-large", nullable=False
    )
    embedding_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sector_slug: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("sectors.slug", name="fk_doc_emb_sector"), nullable=True
    )
    doc_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
