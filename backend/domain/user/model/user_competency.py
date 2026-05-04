from sqlalchemy import Column, String, Integer, Boolean, BigInteger, ForeignKey, DateTime, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..base.database import Base


class UserCompetency(Base):
    """
    사용자 역량 정보 테이블
    사용자의 스킬과 숙련도를 관리하여 역량 갭 분석에 활용
    """
    __tablename__ = "user_competency"
    __table_args__ = (
        Index('idx_user_competency_user_id', 'user_id'),
        Index('idx_user_competency_user_skill', 'user_id', 'skill_name'),
        {"comment": "사용자 역량 정보"},
    )
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="고유 ID")
    user_id = Column(
        BigInteger, 
        ForeignKey('users.id', ondelete='CASCADE'), 
        nullable=False, 
        comment="사용자 식별자"
    )
    skill_name = Column(
        String(100), 
        nullable=False, 
        comment="스킬명 (Python, 기획 등)"
    )
    skill_level = Column(
        Integer, 
        nullable=False, 
        comment="숙련도 (1~5) - 역량 갭(Gap) 분석"
    )
    is_certified = Column(
        Boolean, 
        default=False, 
        nullable=False, 
        comment="자격/경험 여부 - 데이터 신뢰도 보정"
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
        nullable=False,
        comment="수정 시간"
    )
    
    # Relationship (선택사항)
    # user = relationship("User", back_populates="competencies")
    
    def __repr__(self):
        return f"<UserCompetency(id={self.id}, user_id={self.user_id}, skill_name={self.skill_name}, skill_level={self.skill_level})>"
