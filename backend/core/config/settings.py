"""앱 전역 설정 (Pydantic Settings). DB·Redis·JWT·OAuth 등 공통 인프라."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote_plus, urlparse, urlunparse

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/core/config/settings.py 기준
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

if (_PROJECT_ROOT / ".env").exists():
    _ENV_FILE = _PROJECT_ROOT / ".env"
elif (_BACKEND_ROOT / ".env").exists():
    _ENV_FILE = _BACKEND_ROOT / ".env"
else:
    _ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """환경 변수 기반 설정. NEON_*, OAuth, JWT, Redis 키 접두사 포함."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database (Neon PostgreSQL 환경변수 매핑)
    database_url: str = Field(validation_alias="NEON_DATABASE_URL")
    database_user: Optional[str] = Field(default=None, validation_alias="NEON_DATABASE_USER")
    database_password: Optional[str] = Field(default=None, validation_alias="NEON_DATABASE_PASSWORD")

    @field_validator("database_url", mode="before")
    @classmethod
    def convert_jdbc_url(cls, v: str) -> str:
        """JDBC URL을 SQLAlchemy 형식으로 변환 및 asyncpg가 인식하지 못하는 파라미터 제거."""
        if isinstance(v, str) and v.startswith("jdbc:postgresql://"):
            url = v.replace("jdbc:postgresql://", "postgresql+asyncpg://")

            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)

            user = None
            password = None
            if "user" in query_params:
                user = query_params["user"][0]
                del query_params["user"]
            if "password" in query_params:
                password = query_params["password"][0]
                del query_params["password"]

            asyncpg_unsupported_params = [
                "sslmode",
                "channelBinding",
                "sslcert",
                "sslkey",
                "sslrootcert",
                "sslcrl",
                "sslcertmode",
                "application_name",
                "connect_timeout",
                "gssencmode",
                "krbsrvname",
                "service",
            ]

            for param in asyncpg_unsupported_params:
                if param in query_params:
                    del query_params[param]

            netloc = parsed.netloc
            if "@" not in netloc:
                if user and password:
                    user_encoded = quote_plus(user)
                    password_encoded = quote_plus(password)
                    netloc = f"{user_encoded}:{password_encoded}@{netloc}"
                elif user:
                    user_encoded = quote_plus(user)
                    netloc = f"{user_encoded}@{netloc}"

            new_parsed = parsed._replace(netloc=netloc, query="")
            return urlunparse(new_parsed)
        return v

    # Redis (Upstash 등)
    redis_host: str = Field(default="localhost", validation_alias="UPSTASH_REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="UPSTASH_REDIS_PORT")
    redis_password: Optional[str] = Field(default=None, validation_alias="UPSTASH_REDIS_TOKEN")
    redis_ssl_enabled: bool = True

    @field_validator("redis_host", mode="before")
    @classmethod
    def normalize_redis_host(cls, v: object) -> str:
        """
        대시보드에서 REST URL 전체(https://xxxx.upstash.io)를 넣으면
        Redis가 그 문자열 전체를 호스트로 사용해 DNS 조회가 실패한다(Windows: 11001).
        호스트 이름만 남기도록 정규화한다.
        """
        if not isinstance(v, str):
            return str(v) if v is not None else "localhost"
        s = v.strip()
        for prefix in ("https://", "http://"):
            if s.casefold().startswith(prefix):
                s = s[len(prefix) :].lstrip("/")
                break
        if "/" in s:
            s = s.split("/", 1)[0]
        s = s.strip()
        if not s:
            return "localhost"
        return s

    @field_validator("redis_port", mode="before")
    @classmethod
    def convert_redis_port(cls, v) -> int:
        if isinstance(v, str):
            return int(v)
        return v

    # JWT
    jwt_secret: str
    jwt_expiration: int = 1_800_000  # 30분 (밀리초)
    jwt_refresh_expiration: int = 1_814_400_000  # 21일 (밀리초)

    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    google_android_client_id: Optional[str] = None

    # Kakao OAuth
    kakao_client_id: str
    kakao_client_secret: Optional[str] = None
    kakao_redirect_uri: str
    kakao_admin_key: Optional[str] = None

    # Naver OAuth
    naver_client_id: str
    naver_client_secret: str
    naver_redirect_uri: str

    # Open DART (Bronze — raw_economic_data 등)
    dart_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("DART_API_KEY", "OPENDART_API_KEY"),
    )

    # 중소벤처기업부 사업공고 OpenAPI (Bronze — raw_opportunity_data)
    smes_service_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SMES_SERVICE_KEY", "SMES_API_KEY"),
    )

    # ALIO 공공기관 사업정보 OpenAPI (Bronze — raw_economic_data)
    alio_service_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ALIO_SERVICE_KEY", "ALIO_API_KEY"),
    )

    # Bronze 자동 수집 스케줄러 (APScheduler 기반)
    #   - dev: SCHEDULER_ENABLED=false 로 끄고 수동 트리거(/bronze/...) 사용 권장
    #   - prod: true 로 두고 KST 기준 매일 오전 9시 일일 잡 + 월요일 주간 잡
    scheduler_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("SCHEDULER_ENABLED", "BRONZE_SCHEDULER_ENABLED"),
    )
    scheduler_timezone: str = Field(
        default="Asia/Seoul",
        validation_alias=AliasChoices("SCHEDULER_TIMEZONE", "TZ_SCHEDULER"),
    )
    # 일일 잡(DART/MSIT/RSS/SMES) 트리거 시각 — 24h, "HH:MM"
    scheduler_daily_at: str = Field(
        default="09:00",
        validation_alias=AliasChoices("SCHEDULER_DAILY_AT",),
    )
    # 주간 잡(ALIO/Yahoo) 요일 (0=Mon...6=Sun) + 시각
    scheduler_weekly_dow: int = Field(
        default=0,  # Monday
        validation_alias=AliasChoices("SCHEDULER_WEEKLY_DOW",),
    )
    scheduler_weekly_at: str = Field(
        default="09:00",
        validation_alias=AliasChoices("SCHEDULER_WEEKLY_AT",),
    )

    # Redis Key Prefixes
    redis_refresh_token_prefix: str = "refreshToken:"
    redis_user_tokens_prefix: str = "user:tokens:"
    redis_state_prefix: str = "oauth:state:"
    redis_pkce_prefix: str = "oauth:pkce:"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """테스트에서 캐시를 비우고자 하면 get_settings.cache_clear() 호출."""
    return Settings()


settings = get_settings()
