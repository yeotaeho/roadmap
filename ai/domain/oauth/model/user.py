from sqlalchemy import Column, String, DateTime, BigInteger
from sqlalchemy.sql import func
from ..config.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        {"comment": "OAuth 사용자 정보"}
    )
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider = Column(String(20), nullable=False, comment="OAuth 제공자 (kakao, google, naver)")
    provider_id = Column(String(100), nullable=False, comment="OAuth 제공자별 고유 ID")
    email = Column(String(100), nullable=True, comment="이메일")
    name = Column(String(100), nullable=True, comment="이름")
    nickname = Column(String(100), nullable=True, comment="닉네임")
    profile_image = Column(String(500), nullable=True, comment="프로필 이미지 URL")
    role = Column(String(20), default="USER", comment="사용자 권한")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<User(id={self.id}, provider={self.provider}, provider_id={self.provider_id})>"
    
    @classmethod
    def create(cls, provider: str, provider_id: str, email: str = None, 
               name: str = None, nickname: str = None, profile_image: str = None):
        """사용자 생성 헬퍼 메서드"""
        return cls(
            provider=provider,
            provider_id=provider_id,
            email=email,
            name=name,
            nickname=nickname,
            profile_image=profile_image,
            role="USER"
        )

