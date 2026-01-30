import secrets
import hashlib
import base64
import logging
from typing import Optional
import redis.asyncio as redis
from ..config.settings import settings

logger = logging.getLogger(__name__)


class PKCEService:
    """PKCE (Proof Key for Code Exchange) 서비스"""
    
    VERIFIER_EXPIRATION_MINUTES = 10
    CODE_VERIFIER_LENGTH = 128
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = settings.redis_pkce_prefix
    
    def generate_code_verifier(self) -> str:
        """Code Verifier 생성 (43~128자의 랜덤 문자열)"""
        # 128바이트 랜덤 생성
        random_bytes = secrets.token_bytes(self.CODE_VERIFIER_LENGTH)
        
        # Base64 URL 인코딩 (패딩 제거)
        verifier = base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip('=')
        
        # 길이 제한 (128자)
        verifier = verifier[:self.CODE_VERIFIER_LENGTH]
        
        logger.debug(f"Code Verifier 생성 완료: length={len(verifier)}")
        return verifier
    
    def generate_code_challenge(self, code_verifier: str) -> str:
        """Code Challenge 생성 (SHA-256 해시)"""
        # SHA-256 해시
        digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
        
        # Base64 URL 인코딩 (패딩 제거)
        challenge = base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
        
        logger.debug("Code Challenge 생성 완료")
        return challenge
    
    async def store_code_verifier(self, state: str, code_verifier: str) -> None:
        """Code Verifier를 Redis에 저장"""
        key = f"{self.prefix}{state}"
        await self.redis.setex(
            key,
            self.VERIFIER_EXPIRATION_MINUTES * 60,
            code_verifier
        )
        logger.info(f"Code Verifier 저장: state={state}")
    
    async def get_and_remove_code_verifier(self, state: str) -> Optional[str]:
        """Code Verifier를 Redis에서 조회 및 삭제"""
        if not state:
            logger.warn("Code Verifier 조회 실패: state가 null 또는 빈 문자열")
            return None
        
        key = f"{self.prefix}{state}"
        code_verifier = await self.redis.get(key)
        
        if code_verifier:
            # 조회 후 삭제 (재사용 방지)
            await self.redis.delete(key)
            logger.info(f"Code Verifier 조회 및 삭제 성공: state={state}")
            return code_verifier.decode('utf-8')
        
        logger.warn(f"Code Verifier 조회 실패: state={state} (만료되었거나 존재하지 않음)")
        return None

