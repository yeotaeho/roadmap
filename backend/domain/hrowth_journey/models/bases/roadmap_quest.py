# 로드맵 퀘스트 트리 노드 ORM — parent_key 자기참조로 트리 구성

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class RoadmapQuest(Base):
    __tablename__ = "roadmap_quests"
    __table_args__ = (
        UniqueConstraint("roadmap_id", "quest_key", name="uq_roadmap_quest_key"),
        {"comment": "로드맵 퀘스트 트리 노드 — parent_key 자기참조"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    roadmap_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_roadmaps.id", name="fk_roadmap_quest_roadmap", ondelete="CASCADE"),
        nullable=False,
    )
    quest_key: Mapped[str] = mapped_column(String(60), nullable=False)
    parent_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False)
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    state: Mapped[str] = mapped_column(String(12), nullable=False, server_default="available")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
