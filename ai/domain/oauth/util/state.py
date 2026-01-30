import uuid
import logging
from typing import Optional
import redis.asyncio as redis
from ..config.settings import settings

logger = logging.getLogger(__name__)


class OAuthStateService:
    """OAuth State 파라미터 관리 서비스 (CSRF 공격 방지)"""
    
    STATE_EXPIRATION_MINUTES = 10
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = settings.redis_state_prefix
    
    async def generate_and_store_state(self) -> str:
        """State 생성 및 Redis에 저장"""
        state = str(uuid.uuid4())
        key = f"{self.prefix}{state}"
        
        await self.redis.setex(
            key,
            self.STATE_EXPIRATION_MINUTES * 60,
            "valid"
        )
        
        logger.info(f"OAuth State 생성 및 저장: state={state}")
        return state
    
    async def validate_and_remove_state(self, state: str) -> bool:
        """State 검증 (한 번만 사용 가능)"""
        if not state:
            logger.warn("State 검증 실패: state가 null 또는 빈 문자열")
            return False
        
        key = f"{self.prefix}{state}"
        value = await self.redis.get(key)
        
        if value:
            # 검증 성공 후 삭제 (재사용 방지)
            await self.redis.delete(key)
            logger.info(f"OAuth State 검증 성공: state={state}")
            return True
        
        logger.warn(f"OAuth State 검증 실패: state={state} (만료되었거나 존재하지 않음)")
        return False

