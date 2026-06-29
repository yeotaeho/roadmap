# 작업(task) HTTP 라우터 — CRUD 엔드포인트

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.api_guards import get_authenticated_user_id
from domain.task.hub.services.task_service import TaskService
from domain.task.models.transfer.task_dto import (
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
)

router = APIRouter(prefix="/tasks", tags=["task"])


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    data: TaskCreateRequest,
    user_id: str = Depends(get_authenticated_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        svc = TaskService(session)
        task = await svc.create_task(user_id, data)
        await session.commit()
        return task
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    user_id: str = Depends(get_authenticated_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        svc = TaskService(session)
        return await svc.list_tasks(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    user_id: str = Depends(get_authenticated_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        svc = TaskService(session)
        task = await svc.get_task(task_id, user_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    data: TaskUpdateRequest,
    user_id: str = Depends(get_authenticated_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        svc = TaskService(session)
        task = await svc.update_task(task_id, user_id, data)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await session.commit()
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    user_id: str = Depends(get_authenticated_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        svc = TaskService(session)
        deleted = await svc.delete_task(task_id, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Task not found")
        await session.commit()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
