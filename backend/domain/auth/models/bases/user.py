import uuid

from sqlalchemy import Boolean, Column, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_oauth", "auth_provider", "provider_id"),
        {"comment": "사용자 기준 테이블"},
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
        comment="사용자 고유 식별자(UUID)",
    )
    email = Column(String(255), nullable=False, unique=True, comment="로그인 이메일")
    nickname = Column(String(80), nullable=False, comment="서비스 표시 닉네임")
    auth_provider = Column(
        String(20),
        nullable=False,
        server_default=text("'LOCAL'"),
        comment="LOCAL / GOOGLE / KAKAO / NAVER",
    )
    provider_id = Column(String(255), nullable=True, comment="OAuth 제공자 내부 사용자 ID")
    profile_image_url = Column(String(500), nullable=True, comment="프로필 이미지 URL")
    is_active = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="활성/휴면 상태",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        comment="생성 시각",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        comment="수정 시각",
    )

    @property
    def provider(self) -> str:
        return self.auth_provider

    @provider.setter
    def provider(self, value: str) -> None:
        self.auth_provider = value

    @property
    def profile_image(self) -> str | None:
        return self.profile_image_url

    @profile_image.setter
    def profile_image(self, value: str | None) -> None:
        self.profile_image_url = value

    @property
    def name(self) -> str:
        return self.nickname

    @name.setter
    def name(self, value: str) -> None:
        self.nickname = (value or self.nickname or "")[:80]

    @classmethod
    def create(
        cls,
        provider: str,
        provider_id: str,
        email: str,
        nickname: str | None = None,
        profile_image: str | None = None,
    ) -> "User":
        safe_nickname = (nickname or email.split("@")[0] or f"user-{uuid.uuid4().hex[:8]}")[:80]
        return cls(
            auth_provider=provider.upper(),
            provider_id=provider_id,
            email=email,
            nickname=safe_nickname,
            profile_image_url=profile_image,
            is_active=True,
        )
