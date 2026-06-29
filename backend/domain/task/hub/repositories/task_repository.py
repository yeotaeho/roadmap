# 작업(task) DB 접근 레이어

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from domain.task.models.bases.task import Task
from domain.task.models.transfer.task_dto import TaskCreateRequest, TaskUpdateRequest


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: str, data: TaskCreateRequest) -> Task:
        task = Task(
            user_id=uuid.UUID(user_id),
            title=data.title,
            description=data.description,
            status=data.status.value,
            priority=data.priority.value,
            due_date=data.due_date,
        )
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def list_by_user(self, user_id: str) -> List[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.user_id == uuid.UUID(user_id))
            .order_by(Task.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, task_id: int, user_id: str) -> Optional[Task]:
        result = await self.session.execute(
            select(Task).where(Task.id == task_id, Task.user_id == uuid.UUID(user_id))
        )
        return result.scalar_one_or_none()

    async def update(self, task_id: int, user_id: str, data: TaskUpdateRequest) -> Optional[Task]:
        values = {k: v for k, v in data.model_dump(exclude_none=True).items()}
        if "status" in values and hasattr(values["status"], "value"):
            values["status"] = values["status"].value
        if "priority" in values and hasattr(values["priority"], "value"):
            values["priority"] = values["priority"].value

        if not values:
            return await self.get_by_id(task_id, user_id)

        await self.session.execute(
            update(Task)
            .where(Task.id == task_id, Task.user_id == uuid.UUID(user_id))
            .values(**values)
        )
        await self.session.flush()
        return await self.get_by_id(task_id, user_id)

    async def delete(self, task_id: int, user_id: str) -> bool:
        result = await self.session.execute(
            delete(Task).where(Task.id == task_id, Task.user_id == uuid.UUID(user_id))
        )
        return result.rowcount > 0
