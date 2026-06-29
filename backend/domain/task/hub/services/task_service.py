# 작업(task) 유스케이스 서비스

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domain.task.hub.repositories.task_repository import TaskRepository
from domain.task.models.bases.task import Task
from domain.task.models.transfer.task_dto import TaskCreateRequest, TaskUpdateRequest


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = TaskRepository(session)

    async def create_task(self, user_id: str, data: TaskCreateRequest) -> Task:
        return await self._repo.create(user_id, data)

    async def list_tasks(self, user_id: str) -> List[Task]:
        return await self._repo.list_by_user(user_id)

    async def get_task(self, task_id: int, user_id: str) -> Optional[Task]:
        return await self._repo.get_by_id(task_id, user_id)

    async def update_task(self, task_id: int, user_id: str, data: TaskUpdateRequest) -> Optional[Task]:
        return await self._repo.update(task_id, user_id, data)

    async def delete_task(self, task_id: int, user_id: str) -> bool:
        return await self._repo.delete(task_id, user_id)
