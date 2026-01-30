import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from ..config.settings import settings

logger = logging.getLogger(__name__)


class SignupTokenService:
    """회원가입 임시 토큰 유틸리티 (OAuth 정보를 안전하게 전달)"""
    
    ALGORITHM = "HS256"
    SIGNUP_TOKEN_EXPIRATION = 10 * 60 * 1000  # 10분 (밀리초)
    
    def __init__(self):
        self.secret = settings.jwt_secret
    
    def _get_secret_key(self) -> bytes:
        """Secret Key 생성 (HS256 알고리즘을 위한 최소 32바이트)"""
        key_bytes = self.secret.encode('utf-8')
        
        # HS256 알고리즘을 위한 최소 키 크기: 256비트 = 32바이트
        min_key_size = 32
        
        if len(key_bytes) < min_key_size:
            # 키가 너무 짧으면 반복하여 확장
            expanded_key = bytearray(min_key_size)
            for i in range(min_key_size):
                expanded_key[i] = key_bytes[i % len(key_bytes)]
            key_bytes = bytes(expanded_key)
        
        return key_bytes
    
    def generate_signup_token(
        self,
        provider: str,
        provider_id: str,
        email: str,
        name: Optional[str] = None,
        nickname: Optional[str] = None,
        profile_image: Optional[str] = None
    ) -> str:
        """회원가입 토큰 생성"""
        now = datetime.utcnow()
        expiry = now + timedelta(milliseconds=self.SIGNUP_TOKEN_EXPIRATION)
        
        payload = {
            "provider": provider,
            "providerId": provider_id,
            "email": email,
            "name": name,
            "nickname": nickname,
            "profileImage": profile_image,
            "tokenType": "signup",
            "iat": now,
            "exp": expiry
        }
        
        token = jwt.encode(
            payload,
            self._get_secret_key(),
            algorithm=self.ALGORITHM
        )
        
        logger.info(f"회원가입 토큰 생성: provider={provider}, providerId={provider_id}")
        return token
    
    def validate_signup_token(self, token: str) -> Optional[Dict[str, Any]]:
        """회원가입 토큰 검증 및 Claims 추출"""
        try:
            payload = jwt.decode(
                token,
                self._get_secret_key(),
                algorithms=[self.ALGORITHM]
            )
            
            # tokenType 검증
            token_type = payload.get("tokenType")
            if token_type != "signup":
                logger.warn(f"회원가입 토큰 검증 실패: 잘못된 tokenType={token_type}")
                return None
            
            logger.info(f"회원가입 토큰 검증 성공: provider={payload.get('provider')}, providerId={payload.get('providerId')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warn("회원가입 토큰 만료됨")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"회원가입 토큰 검증 실패: {e}")
            return None
    
    def extract_oauth_info(self, claims: Dict[str, Any]) -> Dict[str, str]:
        """Claims에서 OAuth 정보 추출"""
        return {
            "provider": claims.get("provider", ""),
            "providerId": claims.get("providerId", ""),
            "email": claims.get("email", ""),
            "name": claims.get("name", ""),
            "nickname": claims.get("nickname", ""),
            "profileImage": claims.get("profileImage", "")
        }

