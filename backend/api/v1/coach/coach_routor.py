# AI 코치 HTTP 라우터 — 세션 생성·영속 스트리밍·종료·히스토리

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_guards import get_authenticated_user_id
from core.database import get_db
from domain.ai_coach.hub.services.coach_service import CoachService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coach", tags=["coach"])


class CoachStreamRequest(BaseModel):
    sessionId: str
    message: str


@router.post("/sessions")
async def create_session(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """새 코치 대화 세션 생성."""
    session_id = await CoachService(db).create_session(user_id)
    return {"success": True, "sessionId": session_id}


@router.post("/stream")
async def coach_stream(
    request: CoachStreamRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """세션 소유권 검증 후 사용자 메시지+맥락 주입 LLM 응답 SSE 스트리밍."""
    svc = CoachService(db)
    try:
        status = await svc.verify_owner(user_id, request.sessionId)
    except LookupError:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="세션 접근 권한이 없습니다.")
    if status == "ended":
        raise HTTPException(status_code=409, detail="종료된 세션입니다.")
    generator = svc.stream_sse(user_id, request.sessionId, request.message)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: str,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """세션 종료(소유권 검증). 이미 종료면 멱등."""
    try:
        await CoachService(db).end_session(user_id, session_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="세션 접근 권한이 없습니다.")
    return {"success": True}


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """세션 대화 히스토리(소유권 검증)."""
    try:
        messages = await CoachService(db).get_messages(user_id, session_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    except PermissionError:
        raise HTTPException(status_code=403, detail="세션 접근 권한이 없습니다.")
    return {"success": True, "messages": messages}
