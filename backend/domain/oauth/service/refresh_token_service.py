from typing import Optional, Set
import logging
import redis.asyncio as redis
from ..config.settings import settings

logger = logging.getLogger(__name__)


class RefreshTokenService:
    """리프레시 토큰 관리 서비스"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.refresh_token_prefix = settings.redis_refresh_token_prefix
        self.user_tokens_prefix = settings.redis_user_tokens_prefix
        self.refresh_expiration = settings.jwt_refresh_expiration // 1000  # 밀리초 -> 초
    
    async def save_refresh_token(self, user_id: int, refresh_token: str) -> None:
        """리프레시 토큰 저장"""
        try:
            # 토큰을 키로 사용하여 사용자 ID 저장
            token_key = f"{self.refresh_token_prefix}{refresh_token}"
            await self.redis.setex(
                token_key,
                self.refresh_expiration,
                str(user_id)
            )
            
            # 사용자별 토큰 목록에도 추가 (모든 토큰 무효화 시 사용)
            user_tokens_key = f"{self.user_tokens_prefix}{user_id}"
            await self.redis.sadd(user_tokens_key, refresh_token)
            await self.redis.expire(user_tokens_key, self.refresh_expiration)
            
            logger.debug(f"리프레시 토큰 저장 완료: userId={user_id}")
            
        except Exception as e:
            logger.error(f"리프레시 토큰 저장 실패: userId={user_id}, error={e}")
            raise RuntimeError("리프레시 토큰 저장 실패") from e
    
    async def validate_refresh_token(self, refresh_token: str) -> Optional[int]:
        """리프레시 토큰 검증 (Redis에 존재하는지 확인)"""
        try:
            token_key = f"{self.refresh_token_prefix}{refresh_token}"
            user_id_str = await self.redis.get(token_key)
            
            if user_id_str is None:
                logger.warn(
                    f"리프레시 토큰이 Redis에 존재하지 않음: "
                    f"token={refresh_token[:20]}..."
                )
                return None
            
            return int(user_id_str.decode('utf-8'))
            
        except Exception as e:
            logger.error(f"리프레시 토큰 검증 실패: error={e}")
            return None
    
    async def delete_refresh_token(self, refresh_token: str) -> None:
        """리프레시 토큰 삭제 (단일 토큰 무효화)"""
        try:
            token_key = f"{self.refresh_token_prefix}{refresh_token}"
            user_id_str = await self.redis.get(token_key)
            
            if user_id_str:
                user_id = int(user_id_str.decode('utf-8'))
                
                # 토큰 삭제
                await self.redis.delete(token_key)
                
                # 사용자별 토큰 목록에서도 제거
                user_tokens_key = f"{self.user_tokens_prefix}{user_id}"
                await self.redis.srem(user_tokens_key, refresh_token)
                
                logger.info(f"리프레시 토큰 삭제 완료: userId={user_id}")
                
        except Exception as e:
            logger.error(f"리프레시 토큰 삭제 실패: error={e}")
    
    async def invalidate_all_user_tokens(self, user_id: int) -> None:
        """사용자의 모든 리프레시 토큰 무효화 (로그아웃 또는 해킹 위험 시)"""
        try:
            user_tokens_key = f"{self.user_tokens_prefix}{user_id}"
            tokens_bytes = await self.redis.smembers(user_tokens_key)
            
            if tokens_bytes:
                tokens = [token.decode('utf-8') for token in tokens_bytes]
                
                # 모든 토큰 삭제
                for token in tokens:
                    token_key = f"{self.refresh_token_prefix}{token}"
                    await self.redis.delete(token_key)
                
                # 사용자별 토큰 목록도 삭제
                await self.redis.delete(user_tokens_key)
                
                logger.info(
                    f"사용자의 모든 리프레시 토큰 무효화 완료: "
                    f"userId={user_id}, count={len(tokens)}"
                )
                
        except Exception as e:
            logger.error(f"사용자 토큰 무효화 실패: userId={user_id}, error={e}")
            raise RuntimeError("토큰 무효화 실패") from e
    
    async def rotate_refresh_token(
        self,
        user_id: int,
        old_refresh_token: str,
        new_refresh_token: str
    ) -> None:
        """리프레시 토큰 교체 (토큰 로테이션)"""
        try:
            # 이전 토큰 삭제
            await self.delete_refresh_token(old_refresh_token)
            
            # 새 토큰 저장
            await self.save_refresh_token(user_id, new_refresh_token)
            
            logger.info(f"리프레시 토큰 로테이션 완료: userId={user_id}")
            
        except Exception as e:
            logger.error(f"리프레시 토큰 로테이션 실패: userId={user_id}, error={e}")
            raise RuntimeError("토큰 로테이션 실패") from e
    
    async def is_token_valid(self, refresh_token: str) -> bool:
        """특정 토큰이 유효한지 확인"""
        return await self.validate_refresh_token(refresh_token) is not None

