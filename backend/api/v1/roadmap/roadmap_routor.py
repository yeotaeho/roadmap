# Roadmap(전략 로드맵) HTTP 라우터 — 여정 개요·성장 아카이브 서빙(목업 수직 슬라이스)

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_guards import get_authenticated_user_id
from core.database import get_db
from domain.hrowth_journey.hub.services.archive_service import ArchiveService
from domain.hrowth_journey.hub.services.journey_service import JourneyService
from domain.hrowth_journey.hub.services.note_service import NoteService
from domain.hrowth_journey.hub.services.planner_service import PlannerService
from domain.hrowth_journey.hub.services.roadmap_planner_service import RoadmapPlannerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


class GrowthLogUpsertRequest(BaseModel):
    completedQuestIds: list[str] = Field(default_factory=list)
    note: str = ""


def _parse_month(month: str | None) -> tuple[int, int]:
    """YYYY-MM → (year, month). 미지정 시 당월."""
    if not month:
        today = date.today()
        return today.year, today.month
    try:
        parts = month.split("-")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="month 형식은 YYYY-MM 이어야 합니다.")


@router.get("/journey")
async def get_journey(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """여정 개요 — 스킬 트라이앵글·키워드 브릿지 + 퀘스트 트리."""
    try:
        result = await JourneyService(db).get_journey(user_id)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Roadmap 여정 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Roadmap 여정 조회 실패: {str(e)}")


@router.get("/archive")
async def get_archive(
    month: str | None = Query(default=None, description="YYYY-MM (미지정 시 당월)"),
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """성장 아카이브 — 월별 일별 로그(달력 점 표시용)."""
    year, mon = _parse_month(month)
    try:
        result = await ArchiveService(db).get_month(user_id, year, mon)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Roadmap 아카이브 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Roadmap 아카이브 조회 실패: {str(e)}")


@router.put("/archive/{log_date}")
async def upsert_archive_day(
    log_date: str,
    request: GrowthLogUpsertRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """일별 로그 upsert — 달성 퀘스트·자유 기록 영속화."""
    try:
        parsed = datetime.strptime(log_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="날짜 형식은 YYYY-MM-DD 이어야 합니다.")
    try:
        result = await ArchiveService(db).upsert_day(
            user_id, parsed, request.completedQuestIds, request.note
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Roadmap 아카이브 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Roadmap 아카이브 저장 실패: {str(e)}")


@router.post("/refine")
async def refine_roadmap(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """페르소나·목표·관심사 → 개인화 로드맵 재생성(LLM, 폴백 템플릿)."""
    try:
        result = await RoadmapPlannerService(db).generate_for_user(user_id)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Roadmap 생성 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Roadmap 생성 실패: {str(e)}")


# ── 플래너(WBS) — 백로그·스프린트·태스크 ──


def _parse_iso_date(value: str, field: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} 형식은 YYYY-MM-DD 이어야 합니다.")


class SprintCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    goal: str | None = None
    startDate: str
    endDate: str


class SprintPatchRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    goal: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    state: str | None = Field(default=None, pattern="^(planned|active|done)$")
    position: int | None = None


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    sprintId: int | None = None
    questKey: str | None = Field(default=None, max_length=60)
    startDate: str | None = None
    dueDate: str | None = None
    estimatedDays: int | None = Field(default=None, ge=1, le=90)


class TaskPatchRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    sprintId: int | None = None
    questKey: str | None = Field(default=None, max_length=60)
    status: str | None = Field(default=None, pattern="^(todo|doing|done)$")
    startDate: str | None = None
    dueDate: str | None = None
    estimatedDays: int | None = Field(default=None, ge=1, le=90)
    position: int | None = None


class TaskReorderRequest(BaseModel):
    sprintId: int | None = None
    taskIds: list[int] = Field(default_factory=list)


class DecomposeRequest(BaseModel):
    questKey: str = Field(min_length=1, max_length=60)


def _sprint_fields(req: SprintPatchRequest) -> dict:
    """PATCH 부분수정 — 전달된 필드만 snake_case 로 변환."""
    raw = req.model_dump(exclude_unset=True)
    out: dict = {}
    if "title" in raw:
        out["title"] = raw["title"]
    if "goal" in raw:
        out["goal"] = raw["goal"]
    if "startDate" in raw:
        if not raw["startDate"]:
            raise HTTPException(status_code=400, detail="startDate 는 비울 수 없습니다.")
        out["start_date"] = _parse_iso_date(raw["startDate"], "startDate")
    if "endDate" in raw:
        if not raw["endDate"]:
            raise HTTPException(status_code=400, detail="endDate 는 비울 수 없습니다.")
        out["end_date"] = _parse_iso_date(raw["endDate"], "endDate")
    if "state" in raw:
        out["state"] = raw["state"]
    if "position" in raw:
        out["position"] = raw["position"]
    return out


def _task_fields(req: TaskPatchRequest) -> dict:
    raw = req.model_dump(exclude_unset=True)
    out: dict = {}
    for camel, snake in [
        ("title", "title"), ("description", "description"), ("sprintId", "sprint_id"),
        ("questKey", "quest_key"), ("status", "status"), ("estimatedDays", "estimated_days"),
        ("position", "position"),
    ]:
        if camel in raw:
            out[snake] = raw[camel]
    if "startDate" in raw:
        out["start_date"] = _parse_iso_date(raw["startDate"], "startDate") if raw["startDate"] else None
    if "dueDate" in raw:
        out["due_date"] = _parse_iso_date(raw["dueDate"], "dueDate") if raw["dueDate"] else None
    return out


@router.get("/planner")
async def get_planner_board(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """플래너 보드 — 스프린트·태스크 전체를 1회 로드."""
    try:
        result = await PlannerService(db).get_board(user_id)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"플래너 보드 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"플래너 보드 조회 실패: {str(e)}")


@router.post("/planner/sprints")
async def create_sprint(
    request: SprintCreateRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """스프린트 생성."""
    start = _parse_iso_date(request.startDate, "startDate")
    end = _parse_iso_date(request.endDate, "endDate")
    if end < start:
        raise HTTPException(status_code=400, detail="endDate 는 startDate 이후여야 합니다.")
    try:
        sprint = await PlannerService(db).create_sprint(
            user_id, request.title.strip(), request.goal, start, end
        )
        return {"success": True, "sprint": sprint}
    except Exception as e:
        logger.error(f"스프린트 생성 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"스프린트 생성 실패: {str(e)}")


@router.patch("/planner/sprints/{sprint_id}")
async def patch_sprint(
    sprint_id: int,
    request: SprintPatchRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """스프린트 부분 수정."""
    fields = _sprint_fields(request)
    if not fields:
        raise HTTPException(status_code=400, detail="수정할 필드가 없습니다.")
    try:
        ok = await PlannerService(db).update_sprint(user_id, sprint_id, fields)
    except Exception as e:
        logger.error(f"스프린트 수정 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"스프린트 수정 실패: {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="스프린트를 찾을 수 없습니다.")
    return {"success": True}


@router.delete("/planner/sprints/{sprint_id}")
async def delete_sprint(
    sprint_id: int,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """스프린트 삭제 — 소속 태스크는 백로그로 복귀(FK SET NULL)."""
    try:
        ok = await PlannerService(db).delete_sprint(user_id, sprint_id)
    except Exception as e:
        logger.error(f"스프린트 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"스프린트 삭제 실패: {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="스프린트를 찾을 수 없습니다.")
    return {"success": True}


@router.post("/planner/tasks")
async def create_task(
    request: TaskCreateRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """태스크 생성(수동)."""
    fields = {
        "title": request.title.strip(),
        "description": request.description,
        "sprint_id": request.sprintId,
        "quest_key": request.questKey,
        "estimated_days": request.estimatedDays,
        "start_date": _parse_iso_date(request.startDate, "startDate") if request.startDate else None,
        "due_date": _parse_iso_date(request.dueDate, "dueDate") if request.dueDate else None,
    }
    try:
        task = await PlannerService(db).create_task(user_id, fields)
        return {"success": True, "task": task}
    except ValueError:
        raise HTTPException(status_code=404, detail="대상 스프린트를 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"태스크 생성 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"태스크 생성 실패: {str(e)}")


@router.patch("/planner/tasks/{task_id}")
async def patch_task(
    task_id: int,
    request: TaskPatchRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """태스크 부분 수정 — 이동(sprintId)·상태·일정."""
    fields = _task_fields(request)
    if not fields:
        raise HTTPException(status_code=400, detail="수정할 필드가 없습니다.")
    try:
        ok = await PlannerService(db).update_task(user_id, task_id, fields)
    except ValueError:
        raise HTTPException(status_code=404, detail="대상 스프린트를 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"태스크 수정 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"태스크 수정 실패: {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다.")
    return {"success": True}


@router.delete("/planner/tasks/{task_id}")
async def delete_task(
    task_id: int,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """태스크 삭제."""
    try:
        ok = await PlannerService(db).delete_task(user_id, task_id)
    except Exception as e:
        logger.error(f"태스크 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"태스크 삭제 실패: {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다.")
    return {"success": True}


@router.post("/planner/tasks/reorder")
async def reorder_tasks(
    request: TaskReorderRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """드래그 결과 반영 — 대상 컬럼(sprintId)의 태스크 순서를 통째로 재부여."""
    if not request.taskIds:
        raise HTTPException(status_code=400, detail="taskIds 가 비어 있습니다.")
    try:
        moved = await PlannerService(db).reorder_tasks(user_id, request.sprintId, request.taskIds)
        return {"success": True, "moved": moved}
    except ValueError:
        raise HTTPException(status_code=404, detail="대상 스프린트를 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"태스크 재정렬 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"태스크 재정렬 실패: {str(e)}")


@router.post("/planner/decompose")
async def decompose_quest(
    request: DecomposeRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """퀘스트 → AI 태스크 분해(LLM, 폴백 템플릿) → 백로그 추가."""
    try:
        result = await PlannerService(db).decompose(user_id, request.questKey)
    except Exception as e:
        logger.error(f"퀘스트 분해 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"퀘스트 분해 실패: {str(e)}")
    if result["source"] == "none":
        raise HTTPException(status_code=404, detail="해당 퀘스트를 찾을 수 없습니다.")
    return {"success": True, **result}


# ── 노트 — 마크다운 + [[링크]] ──


class NoteCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = ""
    taskId: int | None = None
    questKey: str | None = Field(default=None, max_length=60)


class NoteUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = None
    taskId: int | None = None
    questKey: str | None = Field(default=None, max_length=60)


@router.get("/notes")
async def list_notes(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """노트 목록 — 제목·수정일·미리보기 1줄."""
    try:
        notes = await NoteService(db).list_notes(user_id)
        return {"success": True, "notes": notes}
    except Exception as e:
        logger.error(f"노트 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"노트 목록 조회 실패: {str(e)}")


@router.get("/notes/{note_id}")
async def get_note(
    note_id: int,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """노트 상세 — 본문 + 백링크."""
    try:
        note = await NoteService(db).get_note(user_id, note_id)
    except Exception as e:
        logger.error(f"노트 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"노트 조회 실패: {str(e)}")
    if note is None:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    return {"success": True, "note": note}


@router.post("/notes")
async def create_note(
    request: NoteCreateRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """노트 생성 — 저장 시 [[링크]] 파싱."""
    try:
        note = await NoteService(db).create_note(
            user_id, request.title, request.content, request.taskId, request.questKey
        )
        return {"success": True, "note": note}
    except ValueError:
        raise HTTPException(status_code=409, detail="같은 제목의 노트가 이미 있습니다.")
    except Exception as e:
        logger.error(f"노트 생성 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"노트 생성 실패: {str(e)}")


@router.put("/notes/{note_id}")
async def update_note(
    note_id: int,
    request: NoteUpdateRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """노트 저장 — [[링크]] 재파싱."""
    raw = request.model_dump(exclude_unset=True)
    fields = {
        k_snake: raw[k_camel]
        for k_camel, k_snake in [
            ("title", "title"), ("content", "content"),
            ("taskId", "task_id"), ("questKey", "quest_key"),
        ]
        if k_camel in raw
    }
    try:
        note = await NoteService(db).update_note(user_id, note_id, fields)
    except ValueError:
        raise HTTPException(status_code=409, detail="같은 제목의 노트가 이미 있습니다.")
    except Exception as e:
        logger.error(f"노트 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"노트 저장 실패: {str(e)}")
    if note is None:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    return {"success": True, "note": note}


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: int,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """노트 삭제."""
    try:
        ok = await NoteService(db).delete_note(user_id, note_id)
    except Exception as e:
        logger.error(f"노트 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"노트 삭제 실패: {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    return {"success": True}
