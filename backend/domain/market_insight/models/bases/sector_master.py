# 섹터·서브섹터 마스터 테이블 ORM

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class Sector(Base):
    __tablename__ = "sectors"
    __table_args__ = ({"comment": "섹터 마스터 — slug PK"},)

    slug: Mapped[str] = mapped_column(String(50), primary_key=True)
    name_ko: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SubSector(Base):
    __tablename__ = "sub_sectors"
    __table_args__ = ({"comment": "서브섹터 마스터"},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_slug: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("sectors.slug", name="fk_sub_sector_parent", ondelete="CASCADE"),
        nullable=False,
    )
    name_ko: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
