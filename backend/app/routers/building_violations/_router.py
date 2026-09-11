"""A router whose endpoints are plain functions written against the sync ``Session`` API.

The platform injects an ``AsyncSession`` (dependency ``get_db``); this router wraps every endpoint so that it
executes inside ``AsyncSession.run_sync`` with the underlying sync session - lazy loads, flushes and commits all
work, and the endpoint itself is an ``async def`` as far as FastAPI is concerned.
"""
from __future__ import annotations

import functools
import inspect

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool


def adapt(fn):
    if inspect.iscoroutinefunction(fn) or getattr(fn, "_bvms_adapted", False):
        return fn

    @functools.wraps(fn)
    async def wrapper(**kwargs):
        db = kwargs.get("db")
        if isinstance(db, AsyncSession):
            def call(sync_session):
                kwargs["db"] = sync_session
                return fn(**kwargs)
            return await db.run_sync(call)
        return await run_in_threadpool(fn, **kwargs)

    wrapper._bvms_adapted = True
    return wrapper


class SyncRouter(APIRouter):
    def add_api_route(self, path, endpoint, **kwargs):
        return super().add_api_route(path, adapt(endpoint), **kwargs)
