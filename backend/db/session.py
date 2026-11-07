"""비동기 DB 엔진/세션.

async SQLAlchemy(asyncpg) 기반. 저장/조회 로직은 이 브랜치 범위가 아니며,
후속 담당자가 `get_session` 의존성으로 세션을 주입받아 구현한다.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.api.config import settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    return create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(), class_=AsyncSession, expire_on_commit=False, autoflush=False
    )


def __getattr__(name: str):
    # Preserve explicit admin-script imports without initializing DBs on app import.
    if name == "engine":
        return get_engine()
    if name == "async_session_factory":
        return get_session_factory()
    raise AttributeError(name)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 의존성용 세션 제공자."""
    async with get_session_factory()() as session:
        yield session
