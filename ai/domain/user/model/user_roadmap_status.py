from sqlalchemy import Column, BigInteger, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from ..base.database import Base


class UserRoadmapStatus(Base):
    """
    사용자 로드맵 진행 상태 테이블
    사용자의 학습 로드맵 진행 상황을 추적하여 AI 코치 피드백 제공
    """
    __tablename__ = "user_roadmap_status"
    __table_args__ = (
        Index('idx_user_roadmap_user_id', 'user_id'),
        Index('idx_user_roadmap_last_active', 'last_active_at'),
        Index('idx_user_roadmap_user_trend', 'user_id', 'target_trend_id'),
        {"comment": "사용자 로드맵 진행 상태"},
    )
    
    roadmap_id = Column(
        BigInteger, 
        primary_key=True, 
        autoincrement=True, 
        comment="로드맵 고유 ID"
    )
    user_id = Column(
        BigInteger, 
        ForeignKey('users.id', ondelete='CASCADE'), 
        nullable=False, 
        comment="사용자 식별자"
    )
    target_trend_id = Column(
        Integer, 
        nullable=True, 
        comment="목표로 삼은 트렌드 ID - 세상의 요구 지도와 연결 (trends 테이블 생성 후 ForeignKey 추가 예정)"
    )
    progress_rate = Column(
        Float, 
        default=0.0, 
        nullable=False, 
        comment="학습 진척도 (0~100) - AI 코치의 피드백 근거"
    )
    last_active_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False, 
        comment="최종 활동 시간 - 리마인드 알림 시점 계산"
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
    
    def __repr__(self):
        return f"<UserRoadmapStatus(roadmap_id={self.roadmap_id}, user_id={self.user_id}, progress_rate={self.progress_rate}%)>"
