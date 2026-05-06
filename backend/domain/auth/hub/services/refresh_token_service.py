from typing import Optional

import redis.asyncio as redis

from core.config.settings import settings


class RefreshTokenService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.refresh_token_prefix = settings.redis_refresh_token_prefix
        self.user_tokens_prefix = settings.redis_user_tokens_prefix
        self.refresh_expiration = settings.jwt_refresh_expiration // 1000

    async def save_refresh_token(self, user_id: str, refresh_token: str) -> None:
        token_key = f"{self.refresh_token_prefix}{refresh_token}"
        await self.redis.setex(token_key, self.refresh_expiration, str(user_id))
        user_tokens_key = f"{self.user_tokens_prefix}{user_id}"
        await self.redis.sadd(user_tokens_key, refresh_token)
        await self.redis.expire(user_tokens_key, self.refresh_expiration)

    async def validate_refresh_token(self, refresh_token: str) -> Optional[str]:
        token_key = f"{self.refresh_token_prefix}{refresh_token}"
        user_id_bytes = await self.redis.get(token_key)
        if not user_id_bytes:
            return None
        return user_id_bytes.decode("utf-8")

    async def delete_refresh_token(self, refresh_token: str) -> None:
        token_key = f"{self.refresh_token_prefix}{refresh_token}"
        user_id_bytes = await self.redis.get(token_key)
        if user_id_bytes:
            user_id = user_id_bytes.decode("utf-8")
            await self.redis.delete(token_key)
            user_tokens_key = f"{self.user_tokens_prefix}{user_id}"
            await self.redis.srem(user_tokens_key, refresh_token)

    async def invalidate_all_user_tokens(self, user_id: str) -> None:
        user_tokens_key = f"{self.user_tokens_prefix}{user_id}"
        tokens_bytes = await self.redis.smembers(user_tokens_key)
        if tokens_bytes:
            tokens = [token.decode("utf-8") for token in tokens_bytes]
            for token in tokens:
                token_key = f"{self.refresh_token_prefix}{token}"
                await self.redis.delete(token_key)
            await self.redis.delete(user_tokens_key)

    async def rotate_refresh_token(
        self, user_id: str, old_refresh_token: str, new_refresh_token: str
    ) -> None:
        await self.delete_refresh_token(old_refresh_token)
        await self.save_refresh_token(user_id, new_refresh_token)

    async def is_token_valid(self, refresh_token: str) -> bool:
        return await self.validate_refresh_token(refresh_token) is not None
