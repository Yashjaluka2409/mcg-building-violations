"""Test harness.

* One template SQLite database is built per session (schema + seed_demo); every test gets its own copy,
  its own async engine and one AsyncSession shared by the test body and the API calls it makes.
* API calls go through httpx's ASGI transport; each request runs inside a SAVEPOINT that is rolled back
  when the request fails (the behaviour of the real request scope), so a 4xx leaves no half-written rows.
* Service functions are called with `run(db, fn, ...)`, which executes them inside AsyncSession.run_sync
  exactly as the routers do.
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import httpx
import pytest

os.environ["BVMS_TESTING"] = "1"
os.environ.setdefault("DEMO_MODE", "1")

from app.core import cache  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db import session as S  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models import building_violations  # noqa: E402,F401
from app.services.building_violations import access  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def template_db(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("bvms")
    path = base / "template.sqlite3"
    settings.UPLOADS_DIR = base / "uploads"

    async def build():
        eng = S.rebind(f"sqlite:///{path}")
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        from app.seed import seed_demo
        async with S.session_scope() as db:
            await db.run_sync(lambda s: seed_demo(s, with_cases=False))
        await eng.dispose()
    asyncio.run(build())
    return path


@pytest.fixture
async def db(template_db, tmp_path):
    path = tmp_path / "test.sqlite3"
    shutil.copy(template_db, path)
    settings.UPLOADS_DIR = tmp_path / "uploads"
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    access.invalidate()
    cache.clear()
    S.rebind(f"sqlite:///{path}")
    session = S.AsyncSessionLocal()

    async def override():
        nested = await session.begin_nested()
        try:
            yield session
            if nested.is_active:
                await nested.commit()
        except Exception:
            if nested.is_active:
                await nested.rollback()
            raise

    app.dependency_overrides[S.get_db] = override
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        await session.close()
        await S.engine.dispose()


@pytest.fixture
async def client(db):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver", timeout=120) as c:
        yield c
