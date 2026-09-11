"""Declarative base and column types shared by every model."""
from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

# SQLite has no DECIMAL type; SQLAlchemy converts through float and warns once per column. The demo
# database is SQLite, production is PostgreSQL (native NUMERIC), so the warning carries no information.
warnings.filterwarnings("ignore", message=".*does not support Decimal objects natively.*")


class UTCDateTime(TypeDecorator):
    """Stores UTC; always returns timezone-aware datetimes (SQLite drops the offset, PostgreSQL keeps it)."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class Base(AsyncAttrs, DeclarativeBase):
    """`AsyncAttrs` adds `obj.awaitable_attrs.<relationship>` for code running outside `run_sync`."""


def json_default(o):
    """JSON columns may receive UUIDs, Decimals, dates and datetimes from the services; store them as text."""
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


def json_dumps(o) -> str:
    return json.dumps(o, default=json_default, ensure_ascii=False)
