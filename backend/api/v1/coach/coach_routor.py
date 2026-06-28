# AI 코치 HTTP 라우터 — 사용자 맥락 주입 LLM 멘토링 SSE 스트리밍

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_guards import get_authenticated_user_id
from core.database import get_db
from domain.ai_coach.hub.services.coach_service import CoachService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coach", tags=["coach"])


class CoachStreamRequest(BaseModel):
    message: str


@router.post("/stream")
async def coach_stream(
    request: CoachStreamRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """사용자 메시지 + 페르소나·로드맵·섹터 맥락 → LLM 멘토 응답 SSE 스트리밍."""
    generator = CoachService(db).stream_sse(user_id, request.message)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
