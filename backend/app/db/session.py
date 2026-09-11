"""Async engine and session (sqlalchemy.ext.asyncio), the same wiring as the MCG platform backend.

The request dependency yields an ``AsyncSession``. The module's business logic (services, serializers) is
written against the ordinary ``Session`` API and executed inside ``AsyncSession.run_sync`` - the pattern
SQLAlchemy documents for ORM code that relies on lazy loading. Pool settings follow the platform:
pool_size=25, max_overflow=20, pool_recycle=1800, pool_pre_ping=True.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import json_dumps


def async_url(url: str) -> str:
    """Accept the usual sync URLs in DATABASE_URL and map them to the async drivers (asyncpg / aiosqlite)."""
    for prefix, repl in (("postgresql+psycopg://", "postgresql+asyncpg://"), ("postgresql+psycopg2://", "postgresql+asyncpg://"),
                         ("postgresql://", "postgresql+asyncpg://"), ("postgres://", "postgresql+asyncpg://"), ("sqlite:///", "sqlite+aiosqlite:///")):
        if url.startswith(prefix):
            return repl + url[len(prefix):]
    return url


def make_engine(url: str | None = None) -> AsyncEngine:
    url = async_url(url or settings.sqlalchemy_url)
    if url.startswith("sqlite"):
        eng = create_async_engine(url, json_serializer=json_dumps, pool_pre_ping=True)

        # pysqlite/aiosqlite transaction handling breaks SAVEPOINTs; the documented SQLAlchemy recipe is to
        # take over BEGIN ourselves (isolation_level=None + explicit BEGIN). Also: foreign keys on, WAL mode.
        @event.listens_for(eng.sync_engine, "connect")
        def _sqlite_connect(dbapi_conn, _):
            dbapi_conn.isolation_level = None
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

        @event.listens_for(eng.sync_engine, "begin")
        def _sqlite_begin(conn):
            conn.exec_driver_sql("BEGIN")
        return eng
    return create_async_engine(url, json_serializer=json_dumps, pool_size=settings.DB_POOL_SIZE, max_overflow=settings.DB_MAX_OVERFLOW,
                               pool_recycle=settings.DB_POOL_RECYCLE, pool_pre_ping=True)


engine: AsyncEngine = make_engine()
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=True)


def rebind(url: str) -> AsyncEngine:
    """Point the application at another database (tests use a temporary SQLite file per test)."""
    global engine
    engine = make_engine(url)
    AsyncSessionLocal.configure(bind=engine)
    return engine


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one AsyncSession per request, committed on success, rolled back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def run(db: AsyncSession, fn: Callable, *args, **kwargs):
    """Run a sync service function ``fn(session, ...)`` inside the async session (lazy loads allowed)."""
    return await db.run_sync(lambda s: fn(s, *args, **kwargs))


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """For the CLI and the scheduler: a session that commits on success."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
