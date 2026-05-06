"""SQLAlchemy async 엔진·세션·Base·get_db 의존성 (공통 인프라)."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from core.config.settings import settings

logger = logging.getLogger(__name__)

connect_args: dict = {}

if "neon.tech" in settings.database_url or "neon" in settings.database_url.lower():
    connect_args["ssl"] = True
else:
    connect_args["ssl"] = True

connect_args["server_settings"] = {
    "statement_cache_size": "0",
}

engine = create_async_engine(
    settings.database_url,
    echo=True,
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
)


@event.listens_for(engine.sync_engine, "invalidate")
def on_connection_invalidate(dbapi_conn, connection_record, exception):
    if exception:
        error_str = str(exception)
        if (
            "InvalidCachedStatementError" in error_str
            or "cached statement plan is invalid" in error_str
        ):
            logger.warning(
                "연결 무효화 감지 - InvalidCachedStatementError "
                "(prepared statement 캐시 비활성화 상태에서는 드물어야 함)"
            )


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
