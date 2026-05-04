from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from ..model.user import User
from .base_repository import BaseRepository
import logging

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    """사용자 Repository - BaseRepository의 재시도 로직 상속"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
    
    async def find_by_provider_and_provider_id(
        self, provider: str, provider_id: str
    ) -> List[User]:
        """OAuth 제공자와 제공자 ID로 사용자 찾기"""
        async def _execute():
            result = await self.session.execute(
                select(User)
                .where(User.provider == provider)
                .where(User.provider_id == provider_id)
            )
            return list(result.scalars().all())
        
        return await self._execute_with_retry(_execute)
    
    async def find_by_id(self, user_id: int) -> Optional[User]:
        """사용자 ID로 사용자 찾기"""
        async def _execute():
            result = await self.session.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()
        
        return await self._execute_with_retry(_execute)
    
    async def save(self, user: User) -> User:
        """사용자 저장 (생성 또는 업데이트)"""
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def delete(self, user: User) -> None:
        """사용자 삭제"""
        await self.session.delete(user)
        await self.session.commit()
    
    async def delete_duplicates(self, provider: str, provider_id: str, keep_id: int) -> int:
        """중복 사용자 레코드 삭제 (첫 번째 레코드 제외)"""
        async def _execute():
            result = await self.session.execute(
                select(User)
                .where(User.provider == provider)
                .where(User.provider_id == provider_id)
                .where(User.id != keep_id)
            )
            duplicates = list(result.scalars().all())
            
            for duplicate in duplicates:
                await self.session.delete(duplicate)
            
            await self.session.commit()
            return len(duplicates)
        
        return await self._execute_with_retry(_execute)

