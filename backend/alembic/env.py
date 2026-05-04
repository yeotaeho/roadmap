from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
import asyncio

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from domain.oauth.base.database import Base
from domain.oauth.model.user import User  # Import all models here

# User domain models
from domain.user.model.user_competency import UserCompetency
from domain.user.model.user_roadmap_status import UserRoadmapStatus

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """Get database URL from settings"""
    from domain.oauth.config.settings import settings
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    database_url = get_url()
    
    # SSL 설정 추가 (database.py와 동일한 설정)
    connect_args = {}
    
    # Neon PostgreSQL의 경우 기본적으로 SSL 필요
    if 'neon.tech' in database_url or 'neon' in database_url.lower():
        connect_args['ssl'] = True
    else:
        # 일반 PostgreSQL의 경우도 SSL 활성화 (보안을 위해)
        connect_args['ssl'] = True
    
    # InvalidCachedStatementError 방지: prepared statement 캐시 비활성화
    connect_args['server_settings'] = {
        'statement_cache_size': '0'
    }
    
    # create_async_engine을 직접 사용하여 connect_args 전달
    connectable = create_async_engine(
        database_url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

