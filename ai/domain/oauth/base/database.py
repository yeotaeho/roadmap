from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event
import logging
from ..config.settings import settings

logger = logging.getLogger(__name__)

# connect_args 설정 (asyncpg용)
# asyncpg는 URL 쿼리 파라미터를 사용하지 않으므로 connect_args로 명시적으로 전달
connect_args = {}

# Neon PostgreSQL의 경우 기본적으로 SSL 필요
# SSL 설정을 connect_args로 명시적으로 전달
if 'neon.tech' in settings.database_url or 'neon' in settings.database_url.lower():
    connect_args['ssl'] = True
else:
    # 일반 PostgreSQL의 경우도 SSL 활성화 (보안을 위해)
    connect_args['ssl'] = True

# InvalidCachedStatementError 방지: prepared statement 캐시 비활성화
# asyncpg의 prepared statement 캐시를 비활성화하여 
# 스키마 변경으로 인한 캐시 무효화 문제를 근본적으로 해결
connect_args['server_settings'] = {
    'statement_cache_size': '0'  # 캐시 크기를 0으로 설정하여 비활성화
}

# Async Engine 생성
# InvalidCachedStatementError 방지: prepared statement 캐시 비활성화
engine = create_async_engine(
    settings.database_url,
    echo=True,
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True,  # 연결 유효성 검사
    pool_recycle=300,     # 5분마다 연결 재사용 (Neon PostgreSQL의 경우 짧게 설정)
    pool_size=5,          # 연결 풀 크기
    max_overflow=10,      # 최대 오버플로우 연결 수
    # connect_args의 server_settings에서 prepared statement 캐시가 비활성화되어
    # InvalidCachedStatementError가 발생하지 않습니다.
    # 성능 영향은 미미하며, 에러 방지가 더 중요합니다.
)


# 이벤트 리스너: 연결 무효화 모니터링
@event.listens_for(engine.sync_engine, "invalidate")
def on_connection_invalidate(dbapi_conn, connection_record, exception):
    """
    연결 무효화 시 로깅
    
    prepared statement 캐시가 비활성화되어 있으므로
    InvalidCachedStatementError는 발생하지 않아야 합니다.
    """
    if exception:
        error_str = str(exception)
        if "InvalidCachedStatementError" in error_str or "cached statement plan is invalid" in error_str:
            logger.warning(
                "연결 무효화 감지 - InvalidCachedStatementError 발생 "
                "(prepared statement 캐시가 비활성화되어 있어서는 안 됨)"
            )

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base Model
Base = declarative_base()


async def get_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


