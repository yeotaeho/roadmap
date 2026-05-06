from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domain.auth.hub.repositories.user_repository import UserRepository
from domain.auth.models.bases.user import User


class UserService:
    def __init__(self, session: AsyncSession):
        self.repository = UserRepository(session)

    async def find_or_create_user(
        self,
        provider: str,
        provider_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        nickname: Optional[str] = None,
        profile_image: Optional[str] = None,
    ) -> User:
        if not email:
            raise ValueError("email is required for users table")

        existing_users = await self.repository.find_by_provider_and_provider_id(
            provider, provider_id
        )

        if existing_users:
            user = existing_users[0]
            if len(existing_users) > 1:
                await self.repository.delete_duplicates(provider, provider_id, str(user.id))

            user.email = email
            user.nickname = (nickname or name or user.nickname or email.split("@")[0])[:80]
            user.profile_image_url = profile_image
            user.auth_provider = provider.upper()
            return await self.repository.save(user)

        new_user = User.create(
            provider=provider,
            provider_id=provider_id,
            email=email,
            nickname=(nickname or name),
            profile_image=profile_image,
        )
        return await self.repository.save(new_user)

    async def find_user(self, provider: str, provider_id: str) -> Optional[User]:
        users = await self.repository.find_by_provider_and_provider_id(provider, provider_id)
        return users[0] if users else None

    async def find_by_id(self, user_id: str) -> Optional[User]:
        return await self.repository.find_by_id(user_id)

    async def save(self, user: User) -> User:
        return await self.repository.save(user)
