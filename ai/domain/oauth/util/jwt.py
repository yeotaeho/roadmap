import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from ..config.settings import settings

logger = logging.getLogger(__name__)


class JWTService:
    """JWT 토큰 생성 및 검증 서비스"""
    
    ALGORITHM = "HS512"
    
    def __init__(self):
        self.secret = settings.jwt_secret
        self.expiration = settings.jwt_expiration
        self.refresh_expiration = settings.jwt_refresh_expiration
    
    def _get_secret_key(self) -> bytes:
        """Secret Key 생성 (HS512 알고리즘을 위한 최소 64바이트)"""
        key_bytes = self.secret.encode('utf-8')
        
        # HS512 알고리즘을 위한 최소 키 크기: 512비트 = 64바이트
        min_key_size = 64
        
        if len(key_bytes) < min_key_size:
            # 키가 너무 짧으면 반복하여 확장
            expanded_key = bytearray(min_key_size)
            for i in range(min_key_size):
                expanded_key[i] = key_bytes[i % len(key_bytes)]
            key_bytes = bytes(expanded_key)
            logger.warn(f"JWT secret key was too short. Expanded to {min_key_size} bytes for HS512.")
        
        return key_bytes
    
    def generate_token(
        self, 
        user_id: int, 
        provider: str, 
        email: str, 
        name: Optional[str] = None,
        age: Optional[int] = None
    ) -> str:
        """JWT 액세스 토큰 생성"""
        now = datetime.utcnow()
        expiry = now + timedelta(milliseconds=self.expiration)
        
        payload = {
            "userId": user_id,
            "provider": provider,
            "email": email,
            "name": name,
            "iat": now,
            "exp": expiry,
            "sub": str(user_id)
        }
        
        if age is not None:
            payload["age"] = age
        
        token = jwt.encode(
            payload,
            self._get_secret_key(),
            algorithm=self.ALGORITHM
        )
        
        logger.info(f"JWT 토큰 생성: userId={user_id}")
        return token
    
    def generate_refresh_token(
        self,
        user_id: int,
        provider: str,
        email: str,
        name: Optional[str] = None,
        age: Optional[int] = None
    ) -> str:
        """리프레시 토큰 생성"""
        now = datetime.utcnow()
        expiry = now + timedelta(milliseconds=self.refresh_expiration)
        
        payload = {
            "type": "refresh",
            "userId": user_id,
            "provider": provider,
            "email": email,
            "name": name,
            "iat": now,
            "exp": expiry,
            "sub": str(user_id)
        }
        
        if age is not None:
            payload["age"] = age
        
        token = jwt.encode(
            payload,
            self._get_secret_key(),
            algorithm=self.ALGORITHM
        )
        
        logger.info(f"리프레시 토큰 생성: userId={user_id}")
        return token
    
    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """토큰 디코딩 및 검증"""
        try:
            payload = jwt.decode(
                token,
                self._get_secret_key(),
                algorithms=[self.ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warn("토큰 만료됨")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"토큰 검증 실패: {e}")
            return None
    
    def extract_user_id(self, token: str) -> Optional[int]:
        """토큰에서 사용자 ID 추출"""
        payload = self.decode_token(token)
        if payload:
            user_id = payload.get("userId")
            if isinstance(user_id, int):
                return user_id
            elif isinstance(user_id, str):
                return int(user_id)
        return None
    
    def extract_provider(self, token: str) -> Optional[str]:
        """토큰에서 OAuth 제공자 추출"""
        payload = self.decode_token(token)
        return payload.get("provider") if payload else None
    
    def extract_email(self, token: str) -> Optional[str]:
        """토큰에서 이메일 추출"""
        payload = self.decode_token(token)
        return payload.get("email") if payload else None
    
    def validate_token(self, token: str) -> bool:
        """토큰 유효성 검증"""
        return self.decode_token(token) is not None
    
    def is_token_expired(self, token: str) -> bool:
        """토큰 만료 여부 확인"""
        payload = self.decode_token(token)
        if not payload:
            return True
        
        exp = payload.get("exp")
        if exp:
            return datetime.utcfromtimestamp(exp) < datetime.utcnow()
        return True

