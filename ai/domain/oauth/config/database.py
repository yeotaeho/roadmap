from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from .settings import settings

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

# Async Engine 생성
engine = create_async_engine(
    settings.database_url,
    echo=True,
    future=True,
    connect_args=connect_args
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

