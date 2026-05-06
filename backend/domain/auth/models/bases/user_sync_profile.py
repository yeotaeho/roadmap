from sqlalchemy import Column, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from core.database import Base


class UserSyncProfile(Base):
    __tablename__ = "user_sync_profiles"
    __table_args__ = {"comment": "사용자 명시적 관심사/목표 직무"}

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        comment="사용자 FK",
    )
    target_job = Column(String(100), nullable=True, comment="목표 직무")
    interest_keywords = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="관심 키워드 배열",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        comment="갱신 시각",
    )
