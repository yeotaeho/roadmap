import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.auth.models.bases.user import User

from .base_repository import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def find_by_provider_and_provider_id(
        self, provider: str, provider_id: str
    ) -> List[User]:
        async def _execute():
            result = await self.session.execute(
                select(User)
                .where(User.auth_provider == provider.upper())
                .where(User.provider_id == provider_id)
            )
            return list(result.scalars().all())

        return await self._execute_with_retry(_execute)

    async def find_by_id(self, user_id: str) -> Optional[User]:
        parsed_id = uuid.UUID(str(user_id))

        async def _execute():
            result = await self.session.execute(select(User).where(User.id == parsed_id))
            return result.scalar_one_or_none()

        return await self._execute_with_retry(_execute)

    async def save(self, user: User) -> User:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete_duplicates(self, provider: str, provider_id: str, keep_id: str) -> int:
        keep_uuid = uuid.UUID(str(keep_id))

        async def _execute():
            result = await self.session.execute(
                select(User)
                .where(User.auth_provider == provider.upper())
                .where(User.provider_id == provider_id)
                .where(User.id != keep_uuid)
            )
            duplicates = list(result.scalars().all())
            for duplicate in duplicates:
                await self.session.delete(duplicate)
            await self.session.commit()
            return len(duplicates)

        return await self._execute_with_retry(_execute)
