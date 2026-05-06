from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt

from core.config.settings import settings


class JWTService:
    ALGORITHM = "HS512"

    def __init__(self):
        self.secret = settings.jwt_secret
        self.expiration = settings.jwt_expiration
        self.refresh_expiration = settings.jwt_refresh_expiration

    def _get_secret_key(self) -> bytes:
        key_bytes = self.secret.encode("utf-8")
        min_key_size = 64
        if len(key_bytes) < min_key_size:
            expanded_key = bytearray(min_key_size)
            for i in range(min_key_size):
                expanded_key[i] = key_bytes[i % len(key_bytes)]
            key_bytes = bytes(expanded_key)
        return key_bytes

    def generate_token(
        self,
        user_id: str,
        provider: str,
        email: str,
        name: Optional[str] = None,
    ) -> str:
        now = datetime.utcnow()
        expiry = now + timedelta(milliseconds=self.expiration)
        payload: Dict[str, Any] = {
            "userId": str(user_id),
            "provider": provider,
            "email": email,
            "name": name,
            "iat": now,
            "exp": expiry,
            "sub": str(user_id),
        }
        return jwt.encode(payload, self._get_secret_key(), algorithm=self.ALGORITHM)

    def generate_refresh_token(
        self,
        user_id: str,
        provider: str,
        email: str,
        name: Optional[str] = None,
    ) -> str:
        now = datetime.utcnow()
        expiry = now + timedelta(milliseconds=self.refresh_expiration)
        payload: Dict[str, Any] = {
            "type": "refresh",
            "userId": str(user_id),
            "provider": provider,
            "email": email,
            "name": name,
            "iat": now,
            "exp": expiry,
            "sub": str(user_id),
        }
        return jwt.encode(payload, self._get_secret_key(), algorithm=self.ALGORITHM)

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            return jwt.decode(token, self._get_secret_key(), algorithms=[self.ALGORITHM])
        except jwt.InvalidTokenError:
            return None

    def extract_user_id(self, token: str) -> Optional[str]:
        payload = self.decode_token(token)
        if not payload:
            return None
        user_id = payload.get("userId")
        if user_id is None:
            return None
        return str(user_id)

    def is_token_expired(self, token: str) -> bool:
        payload = self.decode_token(token)
        if not payload:
            return True
        exp = payload.get("exp")
        if exp:
            return datetime.utcfromtimestamp(exp) < datetime.utcnow()
        return True
