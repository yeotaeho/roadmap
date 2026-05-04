from sqlalchemy import Column, String, DateTime, BigInteger, Integer, Float, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from ..base.database import Base


class User(Base):
    """
    OAuth 사용자 정보 테이블
    Google, Kakao, Naver OAuth를 통한 사용자 인증 정보 관리
    """
    __tablename__ = "users"
    __table_args__ = (
        Index('idx_users_provider_provider_id', 'provider', 'provider_id'),
        {"comment": "OAuth 사용자 정보"},
    )
    
    id = Column(
        BigInteger, 
        primary_key=True, 
        autoincrement=True,
        comment="사용자 고유 ID"
    )
    provider = Column(
        String(20), 
        nullable=False, 
        comment="OAuth 제공자 (kakao, google, naver)"
    )
    provider_id = Column(
        String(100), 
        nullable=False, 
        comment="OAuth 제공자별 고유 ID"
    )
    email = Column(
        String(100), 
        nullable=True, 
        comment="이메일"
    )
    name = Column(
        String(100), 
        nullable=True, 
        comment="이름"
    )
    nickname = Column(
        String(100), 
        nullable=True, 
        comment="닉네임"
    )
    profile_image = Column(
        String(500), 
        nullable=True, 
        comment="프로필 이미지 URL"
    )
    age = Column(
        Integer, 
        nullable=True, 
        comment="나이"
    )
    pref_domain_json = Column(
        JSONB, 
        nullable=True, 
        comment="선호 도메인 JSON"
    )
    value_growth = Column(
        Float, 
        nullable=True, 
        comment="성장 가치"
    )
    value_stability = Column(
        Float, 
        nullable=True, 
        comment="안정성 가치"
    )
    value_impact = Column(
        Float, 
        nullable=True, 
        comment="영향력 가치"
    )
    role = Column(
        String(20), 
        default="USER", 
        comment="사용자 권한"
    )
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False,
        comment="생성 시간"
    )
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(),
        nullable=True,
        comment="수정 시간"
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, provider={self.provider}, provider_id={self.provider_id})>"
    
    @classmethod
    def create(cls, provider: str, provider_id: str, email: str = None, 
               name: str = None, nickname: str = None, profile_image: str = None, age: int = None,
               pref_domain_json: dict = None, value_growth: float = None, 
               value_stability: float = None, value_impact: float = None):
        """사용자 생성 헬퍼 메서드"""
        return cls(
            provider=provider,
            provider_id=provider_id,
            email=email,
            name=name,
            nickname=nickname,
            profile_image=profile_image,
            age=age,
            pref_domain_json=pref_domain_json,
            value_growth=value_growth,
            value_stability=value_stability,
            value_impact=value_impact,
            role="USER"
        )

