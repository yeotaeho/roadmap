from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote_plus

# 프로젝트 루트 경로 찾기
# ESG 루트에서 .env 파일을 찾도록 설정 (없으면 ai/ 디렉토리에서 시도)
ESG_ROOT = Path(__file__).parent.parent.parent.parent.parent  # ESG/
AI_ROOT = Path(__file__).parent.parent.parent.parent  # ai/

# ESG 루트에 .env가 있으면 사용, 없으면 ai/ 디렉토리에서 찾기
if (ESG_ROOT / ".env").exists():
    ENV_FILE = ESG_ROOT / ".env"
else:
    ENV_FILE = AI_ROOT / ".env"


class Settings(BaseSettings):
    # Database (Neon PostgreSQL 환경변수 매핑)
    database_url: str = Field(validation_alias="NEON_DATABASE_URL")
    database_user: Optional[str] = Field(default=None, validation_alias="NEON_DATABASE_USER")
    database_password: Optional[str] = Field(default=None, validation_alias="NEON_DATABASE_PASSWORD")
    
    @field_validator("database_url", mode="before")
    @classmethod
    def convert_jdbc_url(cls, v: str) -> str:
        """JDBC URL을 SQLAlchemy 형식으로 변환 및 asyncpg가 인식하지 못하는 파라미터 제거"""
        if isinstance(v, str) and v.startswith("jdbc:postgresql://"):
            # jdbc:postgresql://... -> postgresql+asyncpg://...
            url = v.replace("jdbc:postgresql://", "postgresql+asyncpg://")
            
            # URL 파싱하여 쿼리 파라미터 처리
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # user와 password를 쿼리 파라미터에서 추출 (JDBC URL 형식 대응)
            user = None
            password = None
            if 'user' in query_params:
                user = query_params['user'][0]
                del query_params['user']
            if 'password' in query_params:
                password = query_params['password'][0]
                del query_params['password']
            
            # asyncpg가 인식하지 못하는 파라미터들 제거
            asyncpg_unsupported_params = [
                'sslmode', 'channelBinding', 'sslcert', 'sslkey', 
                'sslrootcert', 'sslcrl', 'sslcertmode', 'application_name',
                'connect_timeout', 'gssencmode', 'krbsrvname', 'service'
            ]
            
            for param in asyncpg_unsupported_params:
                if param in query_params:
                    del query_params[param]
            
            # user와 password가 쿼리 파라미터에서 추출되었다면 URL에 포함
            if user or password:
                # URL에 user:password@ 형식으로 추가
                netloc = parsed.netloc
                if '@' not in netloc:  # 이미 user:password@ 형식이 아닌 경우
                    if user and password:
                        # URL 인코딩 (특수문자 처리)
                        user_encoded = quote_plus(user)
                        password_encoded = quote_plus(password)
                        netloc = f"{user_encoded}:{password_encoded}@{netloc}"
                    elif user:
                        user_encoded = quote_plus(user)
                        netloc = f"{user_encoded}@{netloc}"
            
            # 모든 쿼리 파라미터 제거 (asyncpg는 URL 파라미터를 사용하지 않음)
            new_parsed = parsed._replace(netloc=netloc, query='')
            url = urlunparse(new_parsed)
            
            return url
        return v
    
    # Redis (Upstash Redis 환경변수 매핑)
    redis_host: str = Field(default="localhost", validation_alias="UPSTASH_REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="UPSTASH_REDIS_PORT")
    redis_password: Optional[str] = Field(default=None, validation_alias="UPSTASH_REDIS_TOKEN")
    redis_ssl_enabled: bool = True
    
    @field_validator("redis_port", mode="before")
    @classmethod
    def convert_redis_port(cls, v) -> int:
        """Redis 포트를 정수로 변환"""
        if isinstance(v, str):
            return int(v)
        return v
    
    # JWT
    jwt_secret: str
    jwt_expiration: int = 1800000  # 30분 (밀리초)
    jwt_refresh_expiration: int = 1814400000  # 21일 (밀리초)
    
    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    
    # Kakao OAuth
    kakao_client_id: str
    kakao_client_secret: Optional[str] = None
    kakao_redirect_uri: str
    kakao_admin_key: Optional[str] = None
    
    # Naver OAuth
    naver_client_id: str
    naver_client_secret: str
    naver_redirect_uri: str
    
    # Redis Key Prefixes
    redis_refresh_token_prefix: str = "refreshToken:"
    redis_user_tokens_prefix: str = "user:tokens:"
    redis_state_prefix: str = "oauth:state:"
    redis_pkce_prefix: str = "oauth:pkce:"
    
    class Config:
        env_file = str(ENV_FILE)  # 절대 경로 사용
        case_sensitive = False
        extra = "ignore"  # 정의되지 않은 환경변수 무시


settings = Settings()

