"""Small ORM conveniences shared by services and routers."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session


def get_or_create(db: Session, model, defaults: dict | None = None, **kw):
    obj = db.query(model).filter_by(**kw).first()
    if obj:
        return obj, False
    obj = model(**kw, **(defaults or {}))
    db.add(obj)
    db.flush()
    return obj, True


def update_or_create(db: Session, model, defaults: dict | None = None, **kw):
    obj = db.query(model).filter_by(**kw).first()
    created = obj is None
    if created:
        obj = model(**kw)
        db.add(obj)
    for k, v in (defaults or {}).items():
        setattr(obj, k, v)
    db.flush()
    return obj, created


def to_uuid(v) -> uuid.UUID | None:
    if v is None or v == "":
        return None
    if isinstance(v, uuid.UUID):
        return v
    try:
        return uuid.UUID(str(v))
    except (ValueError, AttributeError, TypeError):
        return None


def uuids(values) -> list[uuid.UUID]:
    return [u for u in (to_uuid(v) for v in (values or [])) if u is not None]


def client_ip(request) -> str | None:
    """First X-Forwarded-For hop (set by the tunnel / reverse proxy) or the socket peer."""
    if request is None:
        return None
    xff = request.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else None)
    return ip or None


def device_id_of(request) -> str:
    return (request.headers.get("x-device-id", "") if request is not None else "") or ""


def jsonable(v):
    """Round-trip through JSON so that everything stored in a JSON column is plain (UUID/Decimal/date -> str)."""
    return json.loads(json.dumps(v, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o)))


def dec(v, places: int | None = None) -> Decimal | None:
    if v is None or v == "":
        return None
    d = v if isinstance(v, Decimal) else Decimal(str(v))
    if places is not None:
        d = d.quantize(Decimal(1).scaleb(-places))
    return d
