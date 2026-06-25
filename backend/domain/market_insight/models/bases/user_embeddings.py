# Silver — 사용자 관심·직무 임베딩(halfvec 3072, Sync 입력) ORM

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class UserEmbeddings(Base):
    __tablename__ = "user_embeddings"
    __table_args__ = ({"comment": "Silver — 사용자 관심·직무 임베딩(halfvec 3072, Sync 입력)"},)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_user_emb_user", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[float]] = mapped_column(HALFVEC(3072), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    embedding_model: Mapped[str] = mapped_column(
        String(60), server_default="text-embedding-3-large", nullable=False
    )
    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
