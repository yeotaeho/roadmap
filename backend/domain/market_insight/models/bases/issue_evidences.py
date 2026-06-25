# Gold — Gap 이슈 근거(원천 기사/리포트 링크) ORM

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class IssueEvidences(Base):
    __tablename__ = "issue_evidences"
    __table_args__ = (
        Index("ix_issue_evidences_issue", "issue_id"),
        {"comment": "Gold — Gap 이슈 근거(원천 기사/리포트 링크)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("gap_issues.id", name="fk_issue_evidences_issue", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_table_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
