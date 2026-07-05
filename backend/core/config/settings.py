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

    # 내부 운영 토큰 — refine/match 배치 트리거 엔드포인트 가드용.
    #   미설정 시 해당 엔드포인트는 fail-closed(503)로 전면 차단된다.
    #   로컬 개발에서 수동 트리거하려면 .env 에 INTERNAL_API_KEY 설정.
    internal_api_key: Optional[str] = Field(
        default=None, validation_alias="INTERNAL_API_KEY"
    )

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

    # LLM (Silver — raw_economic/discourse 자유 텍스트 섹터 분류)
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    llm_classify_model: str = Field(
        default="gpt-4o-mini", validation_alias="LLM_CLASSIFY_MODEL"
    )
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")
    user_llm_provider: str = Field(default="gemini", validation_alias="USER_LLM_PROVIDER")
    user_llm_model: str = Field(default="", validation_alias="USER_LLM_MODEL")
    llm_classify_confidence_min: float = Field(
        default=0.6, validation_alias="LLM_CLASSIFY_CONFIDENCE_MIN"
    )
    tech_demand_youth_fit_min: float = Field(
        default=0.4, validation_alias="TECH_DEMAND_YOUTH_FIT_MIN"
    )
    llm_embed_model: str = Field(
        default="text-embedding-3-large", validation_alias="LLM_EMBED_MODEL"
    )
    llm_embed_dim: int = Field(default=3072, validation_alias="LLM_EMBED_DIM")

    # AI 코치 LLM (Claude Sonnet — tool-calling)
    anthropic_api_key: Optional[str] = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    coach_llm_model: str = Field(default="claude-sonnet-5", validation_alias="COACH_LLM_MODEL")

    # 코치 웹 tool (C-2)
    tavily_api_key: Optional[str] = Field(default=None, validation_alias="TAVILY_API_KEY")
    watercrawl_api_key: Optional[str] = Field(default=None, validation_alias="WATERCRAWL_API_KEY")

    # Pulse 방향성 modifier 튜닝(감성·시장 방향 가산 이동) — 실사용 데이터 축적 후 .env 로 재조정.
    pulse_sentiment_k: float = Field(default=15.0, validation_alias="PULSE_SENTIMENT_K")
    pulse_modifier_window_days: int = Field(
        default=7, validation_alias="PULSE_MODIFIER_WINDOW_DAYS"
    )
    pulse_modifier_shrink_k: float = Field(default=8.0, validation_alias="PULSE_MODIFIER_SHRINK_K")
    pulse_text_axis_weight: float = Field(default=1.0, validation_alias="PULSE_TEXT_AXIS_WEIGHT")
    pulse_market_axis_weight: float = Field(
        default=1.0, validation_alias="PULSE_MARKET_AXIS_WEIGHT"
    )
    pulse_center_text_sentiment: bool = Field(
        default=True, validation_alias="PULSE_CENTER_TEXT_SENTIMENT"
    )

    # 시장 전망(TimesFM 14일 예측) 튜닝 — 실사용 후 .env 로 재조정.
    forecast_horizon_days: int = Field(default=14, validation_alias="FORECAST_HORIZON_DAYS")
    forecast_score_k: float = Field(default=5.0, validation_alias="FORECAST_SCORE_K")
    forecast_up_threshold: float = Field(default=1.5, validation_alias="FORECAST_UP_THRESHOLD")
    forecast_up_strong_threshold: float = Field(
        default=5.0, validation_alias="FORECAST_UP_STRONG_THRESHOLD"
    )
    forecast_min_history: int = Field(default=64, validation_alias="FORECAST_MIN_HISTORY")
    forecast_band_norm: float = Field(default=0.3, validation_alias="FORECAST_BAND_NORM")
    forecast_model_repo: str = Field(
        default="google/timesfm-2.5-200m-pytorch", validation_alias="FORECAST_MODEL_REPO"
    )

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

    # 한국은행 ECOS OpenAPI (Bronze — raw_economic_data, 거시 자금 흐름)
    #   발급: https://ecos.bok.or.kr/api/#/AuthKeyApply
    bok_ecos_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("BOK_ECOS_API_KEY", "BOK_ECOS_SERVICE_KEY"),
    )

    # 보조금24/공공서비스 정보 OpenAPI (Bronze — raw_economic_data, 정부→민간 보조금)
    #   발급: https://www.data.go.kr/data/15113968/openapi.do
    subsidy24_service_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SUBSIDY24_SERVICE_KEY", "SUBSIDY24_API_KEY"),
    )

    # KIPRIS PLUS 특허 검색 API (Bronze — raw_economic_data, 기술 분야별 특허 출원 트렌드)
    #   발급: https://plus.kipris.or.kr → 서비스 신청 → ServiceKey 파라미터로 사용
    kipris_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("KIPRIS_API_KEY", "KIPRIS_SERVICE_KEY"),
    )

    github_token: Optional[str] = Field(default=None, validation_alias="GITHUB_TOKEN")
    worknet_api_key: Optional[str] = Field(default=None, validation_alias="WORKNET_API_KEY")
    hrdnet_api_key: Optional[str] = Field(default=None, validation_alias="HRDNET_API_KEY")
    goyong24_recruit_api_key: Optional[str] = Field(
        default=None, validation_alias="GOYONG24_RECRUIT_API_KEY"
    )
    goyong24_employer_training_api_key: Optional[str] = Field(
        default=None, validation_alias="GOYONG24_EMPLOYER_TRAINING_API_KEY"
    )
    goyong24_senior_program_api_key: Optional[str] = Field(
        default=None, validation_alias="GOYONG24_SENIOR_PROGRAM_API_KEY"
    )
    goyong24_duty_info_api_key: Optional[str] = Field(
        default=None, validation_alias="GOYONG24_DUTY_INFO_API_KEY"
    )
    goyong24_national_hrd_consortium_api_key: Optional[str] = Field(
        default=None,
        validation_alias="GOYONG24_NATIONAL_HRD_CONSORTIUM_API_KEY",
    )
    saramin_access_key: Optional[str] = Field(
        default=None, validation_alias="SARAMIN_ACCESS_KEY"
    )

    # 관세청 수출입무역통계 OpenAPI (Bronze — raw_innovation_data, HS코드별 월간 수출금액)
    #   발급: https://www.data.go.kr → "관세청 수출입무역통계" 검색 → 서비스 신청
    customs_service_key: Optional[str] = Field(
        default=None, validation_alias="CUSTOMS_SERVICE_KEY"
    )

    # 커리어넷 Open API (Bronze — raw_people_data, 직업정보 일자리전망·학과정보)
    #   발급: https://www.career.go.kr Open API 센터 → 인증키 발급
    careernet_api_key: Optional[str] = Field(
        default=None, validation_alias="CAREERNET_API_KEY"
    )

    # 창업진흥원 K-Startup 통합공고 OpenAPI (Bronze — raw_opportunity_data, 정부 창업지원 사업공고)
    #   발급: https://www.data.go.kr/data/15125364/openapi.do
    #   data.go.kr 계열 키는 계정당 동일 인코딩키이므로 DATA_GO_KR_SERVICE_KEY 로 일괄 재사용 가능.
    kstartup_service_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("KSTARTUP_SERVICE_KEY", "DATA_GO_KR_SERVICE_KEY"),
    )

    # 조달청 나라장터 입찰공고정보 OpenAPI (Bronze — raw_opportunity_data, 정부→민간 자본 흐름)
    #   발급: https://www.data.go.kr/data/15129394/openapi.do
    narajangteo_service_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "NARAJANGTEO_SERVICE_KEY", "G2B_SERVICE_KEY", "DATA_GO_KR_SERVICE_KEY"
        ),
    )

    # 중소벤처기업부 벤처기업명단 (Bronze — verified_company_master, 정부 인증 기업)
    #   발급: https://www.data.go.kr/data/15084581/openapi.do (fileData→OpenAPI 자동변환)
    venture_list_service_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("VENTURE_LIST_SERVICE_KEY", "DATA_GO_KR_SERVICE_KEY"),
    )
    # odcloud uddi 리소스 경로(배포 월마다 변경). 미설정 시 컬렉터 _DEFAULT_RESOURCE 사용.
    venture_list_resource: Optional[str] = Field(
        default=None, validation_alias="VENTURE_LIST_RESOURCE"
    )

    # KIAT 기술은행 수요기술 조회 서비스 (Bronze — raw_innovation_data, TECH_DEMAND_SIGNAL)
    #   data.go.kr/15158929 (_GW REST). 사용자가 키를 TECH_DEMAND_SIGNAL 로 등록.
    kiat_tech_demand_service_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("TECH_DEMAND_SIGNAL", "KIAT_TECH_DEMAND_SERVICE_KEY", "DATA_GO_KR_SERVICE_KEY"),
    )

    # 영화진흥위원회(KOBIS) 일별 박스오피스 OpenAPI 키 (Bronze — raw_economic_data, 콘텐츠 수요)
    #   발급: https://www.kobis.or.kr/kobisopenapi/ 무료 회원가입 → 키 발급. data.go.kr 계열 아님.
    kobis_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("KOBIS_API_KEY", "KOBIS_SERVICE_KEY"),
    )

    # NCS 국가직무능력표준 기준정보 조회 (data.go.kr 15128213, 역량 온톨로지 마스터)
    ncs_standard_service_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("NCS_STANDARD_SERVICE_KEY", "DATA_GO_KR_SERVICE_KEY"),
    )
    # NCS 관련 정보 (data.go.kr 15063879, 능력단위 정의·자격 연계 보충)
    ncs_info_service_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("NCS_INFO_SERVICE_KEY", "DATA_GO_KR_SERVICE_KEY"),
    )

    # 온통청년 OpenAPI (youthcenter.go.kr, Chance 탭 청년 기회 인벤토리)
    # 인증 파라미터: openApiVlak (UUID 36자), 응답: XML
    # BASE_URL: https://www.youthcenter.go.kr/opi/
    youth_policy_service_key: Optional[str] = Field(
        default=None,
        validation_alias="YOUTH_POLICY_SERVICE_KEY",
    )
    youth_center_service_key: Optional[str] = Field(
        default=None,
        validation_alias="YOUTH_CENTER_SERVICE_KEY",
    )
    youth_content_service_key: Optional[str] = Field(
        default=None,
        validation_alias="YOUTH_CONTENT_SERVICE_KEY",
    )
    youth_basic_plan_service_key: Optional[str] = Field(
        default=None,
        validation_alias="YOUTH_BASIC_PLAN_SERVICE_KEY",
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
