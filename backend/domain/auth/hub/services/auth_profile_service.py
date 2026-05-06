import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.auth.models.bases.user import User
from domain.auth.models.bases.user_sync_profile import UserSyncProfile


class AuthProfileService:
    """
    Auth 도메인에서 회원가입/로그인 직후 프로필 보정과
    기본 프로필, sync 프로필 업서트를 통합 관리한다.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_profile_defaults(
        self,
        user: User,
        *,
        nickname_hint: Optional[str] = None,
        profile_image_url: Optional[str] = None,
    ) -> User:
        if not user.nickname:
            user.nickname = (nickname_hint or user.email.split("@")[0])[:80]
        if profile_image_url:
            user.profile_image_url = profile_image_url
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_basic_profile(
        self,
        user_id: str,
        *,
        nickname: Optional[str] = None,
        profile_image_url: Optional[str] = None,
    ) -> User:
        user_uuid = uuid.UUID(user_id)
        result = await self.session.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError("user not found")
        if nickname is not None:
            user.nickname = nickname[:80]
        if profile_image_url is not None:
            user.profile_image_url = profile_image_url
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_sync_profile(self, user_id: str) -> Optional[UserSyncProfile]:
        user_uuid = uuid.UUID(user_id)
        result = await self.session.execute(
            select(UserSyncProfile).where(UserSyncProfile.user_id == user_uuid)
        )
        return result.scalar_one_or_none()

    async def upsert_sync_profile(
        self,
        user_id: str,
        *,
        target_job: Optional[str],
        interest_keywords: list[str],
    ) -> UserSyncProfile:
        user_uuid = uuid.UUID(user_id)
        profile = await self.get_sync_profile(user_id)
        if profile is None:
            profile = UserSyncProfile(
                user_id=user_uuid,
                target_job=target_job,
                interest_keywords=interest_keywords or [],
            )
            self.session.add(profile)
        else:
            profile.target_job = target_job
            profile.interest_keywords = interest_keywords or []
        await self.session.commit()
        await self.session.refresh(profile)
        return profile
