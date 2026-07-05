# ai_coach ORM 모델 집합 — alembic 메타데이터 등록용 re-export

from domain.ai_coach.models.bases.coach_message import CoachMessage
from domain.ai_coach.models.bases.coach_session import CoachSession

__all__ = ["CoachSession", "CoachMessage"]
