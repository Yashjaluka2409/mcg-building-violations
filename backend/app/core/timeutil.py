"""Time helpers: the database stores UTC; display and financial years use the Corporation's zone (Asia/Kolkata)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings

UTC = timezone.utc
LOCAL_TZ = ZoneInfo(settings.TIME_ZONE)


def now() -> datetime:
    return datetime.now(UTC)


def aware(dt: datetime | None) -> datetime | None:
    """Make a datetime timezone-aware (naive values are taken as UTC, which is how they are stored)."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def localtime(dt: datetime | None = None) -> datetime | None:
    if dt is None:
        return now().astimezone(LOCAL_TZ)
    return aware(dt).astimezone(LOCAL_TZ)


def localdate() -> date:
    return localtime().date()


def make_aware_local(dt: datetime) -> datetime:
    """Interpret a naive datetime as local (Asia/Kolkata) wall-clock time."""
    return dt.replace(tzinfo=LOCAL_TZ) if dt.tzinfo is None else dt


def as_date(v) -> date | None:
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])
