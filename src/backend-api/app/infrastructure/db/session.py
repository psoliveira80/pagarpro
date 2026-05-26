from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.settings import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_sync_engine = None
_sync_sessionmaker: sessionmaker[Session] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.APP_ENV == "dev",
            pool_size=20,
            max_overflow=10,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _sessionmaker


def get_sync_sessionmaker() -> sessionmaker[Session]:
    """Return a synchronous sessionmaker for Celery tasks."""
    global _sync_engine, _sync_sessionmaker
    if _sync_sessionmaker is None:
        settings = get_settings()
        # Convert async URL to sync (asyncpg -> psycopg2)
        sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
        _sync_engine = create_sync_engine(sync_url, pool_size=5, max_overflow=5)
        _sync_sessionmaker = sessionmaker(bind=_sync_engine, expire_on_commit=False)
    return _sync_sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
