import json
import logging
import uuid
from typing import Any, Dict, Optional

import redis.asyncio as redis

from core.config.settings import settings

logger = logging.getLogger(__name__)


class OAuthStateService:
    """OAuth State 파라미터 관리 서비스 (CSRF 공격 방지)"""

    STATE_EXPIRATION_MINUTES = 10

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = settings.redis_state_prefix

    async def generate_and_store_state(
        self,
        mode: Optional[str] = None,
        client: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ) -> str:
        """State 생성 및 Redis에 저장 (mode/client/redirect_uri 포함)"""
        state = str(uuid.uuid4())
        key = f"{self.prefix}{state}"

        state_data: Dict[str, Any] = {"valid": True}
        if mode:
            state_data["mode"] = mode
        if client:
            state_data["client"] = client
        if redirect_uri:
            state_data["redirect_uri"] = redirect_uri

        await self.redis.setex(
            key,
            self.STATE_EXPIRATION_MINUTES * 60,
            json.dumps(state_data),
        )

        logger.info(
            f"OAuth State 생성 및 저장: state={state}, mode={mode}, client={client}"
        )
        return state

    async def validate_and_remove_state(self, state: str) -> Optional[Dict[str, Any]]:
        """State 검증 및 mode 정보 반환 (한 번만 사용 가능)"""
        if not state:
            logger.warn("State 검증 실패: state가 null 또는 빈 문자열")
            return None

        key = f"{self.prefix}{state}"
        value = await self.redis.get(key)

        if value:
            try:
                state_data = json.loads(value)
                await self.redis.delete(key)
                logger.info(
                    f"OAuth State 검증 성공: state={state}, mode={state_data.get('mode')}"
                )
                return state_data
            except json.JSONDecodeError:
                await self.redis.delete(key)
                logger.info(f"OAuth State 검증 성공 (기존 형식): state={state}")
                return {"valid": True}

        logger.warn(f"OAuth State 검증 실패: state={state} (만료되었거나 존재하지 않음)")
        return None
