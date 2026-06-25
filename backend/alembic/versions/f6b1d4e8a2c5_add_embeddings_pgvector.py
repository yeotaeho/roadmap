"""pgvector 활성화 + document_embeddings·user_embeddings(halfvec 3072) 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy.dialects import postgresql


revision: str = "f6b1d4e8a2c5"
down_revision: Union[str, None] = "e5a9c3f7b1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── 문서/소스 임베딩 (RAG·섹터 대표 벡터) ──
    op.create_table(
        "document_embeddings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_table", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("embedding", HALFVEC(3072), nullable=False),
        sa.Column(
            "embedding_model",
            sa.String(length=60),
            server_default=sa.text("'text-embedding-3-large'"),
            nullable=False,
        ),
        sa.Column("embedding_version", sa.String(length=40), nullable=True),
        sa.Column("sector_slug", sa.String(length=50), nullable=True),
        sa.Column("doc_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["sector_slug"], ["sectors.slug"], name="fk_doc_emb_sector"),
        sa.UniqueConstraint(
            "source_table", "source_id", "chunk_index", "embedding_model",
            name="uq_doc_emb_source",
        ),
        comment="Silver/RAG — 소스 텍스트 임베딩(halfvec 3072, 섹터 대표·검색)",
    )
    op.create_index("ix_doc_emb_sector", "document_embeddings", ["sector_slug"])
    # HNSW 코사인 인덱스 (halfvec ops).
    op.execute(
        "CREATE INDEX ix_document_embeddings_hnsw "
        "ON document_embeddings USING hnsw (embedding halfvec_cosine_ops)"
    )

    # ── 사용자 임베딩 (Sync 입력) ──
    op.create_table(
        "user_embeddings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding", HALFVEC(3072), nullable=False),
        sa.Column("source_version", sa.String(length=40), nullable=True),
        sa.Column(
            "embedding_model",
            sa.String(length=60),
            server_default=sa.text("'text-embedding-3-large'"),
            nullable=False,
        ),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_emb_user", ondelete="CASCADE"
        ),
        comment="Silver — 사용자 관심·직무 임베딩(halfvec 3072, Sync 입력)",
    )


def downgrade() -> None:
    op.drop_table("user_embeddings")
    op.drop_index("ix_document_embeddings_hnsw", table_name="document_embeddings")
    op.drop_index("ix_doc_emb_sector", table_name="document_embeddings")
    op.drop_table("document_embeddings")
