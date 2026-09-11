"""Shared test helpers (the equivalents of Django's ORM shortcuts used by the previous test suite)."""
from __future__ import annotations

from app.core.security import create_access_token
from app.core.timeutil import now
from app.models import building_violations as m
from app.services.building_violations import access
from app.services.building_violations import workflow as wf
from app.services.building_violations.media import create_attachment

BASE = "/building-violations/api"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00"
       b"\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
CLEAN = {"source": "app", "platform": "android", "native_module": True, "is_physical_device": True, "rooted": False, "developer_options": False,
         "mock_location": False, "vpn_active": False, "proxy_configured": False, "fix_age_s": 2, "jitter_m": 0.8, "app_version": "1.0.0", "device_model": "Pixel 8"}


async def run(db, fn, *args, **kwargs):
    """Run a sync service function fn(session, ...) inside the async session (lazy loads allowed)."""
    return await db.run_sync(lambda s: fn(s, *args, **kwargs))


def hdr(user) -> dict:
    prof = getattr(user, "bvms_profile", None)
    return {"Authorization": f"Bearer {create_access_token(user.id, [prof.role] if prof else [])}"}


async def officer(db, role=None, **flt):
    def q(s):
        qq = s.query(m.OfficerProfile)
        if role:
            qq = qq.filter(m.OfficerProfile.role == role)
        for k, v in flt.items():
            qq = qq.filter(getattr(m.OfficerProfile, k) == v)
        u = qq.order_by(m.OfficerProfile.id).first().user
        u.bvms_profile  # noqa: B018 - load the profile now (the auth header and role checks read it outside the session)
        return u
    return await run(db, q)


async def ward(db, number: int):
    return await run(db, lambda s: s.query(m.Ward).filter(m.Ward.number == number).one())


async def get(db, model, **flt):
    return await run(db, lambda s: s.query(model).filter_by(**flt).first())


async def count(db, model, **flt):
    return await run(db, lambda s: s.query(model).filter_by(**flt).count())


async def latest(db, model, col="at"):
    return await run(db, lambda s: s.query(model).order_by(getattr(model, col).desc(), model.id.desc()).first())


async def attr(db, obj, path: str):
    """Resolve a dotted attribute path (lazy loads included) inside run_sync."""
    def f(s):
        v = obj
        for part in path.split("."):
            v = getattr(v, part)
            if callable(v) and part.startswith("get_"):
                v = v()
        return v
    return await run(db, f)


async def refresh(db, *objs):
    for o in objs:
        await db.refresh(o)


async def events(db, case) -> list[str]:
    return await run(db, lambda s: [e.action for e in s.query(m.CaseEvent).filter(m.CaseEvent.case_id == case.id).order_by(m.CaseEvent.at, m.CaseEvent.id)])


def set_setting(s, key: str, value):
    row = s.get(m.WorkflowSetting, key)
    row.value = value
    s.flush()
    access.invalidate()


def add_media(s, case, lat, lng, user, kind="INSPECTION", task=None):
    """Store a placeholder geotagged photo and attach it to the case (like the Django `_media` helper)."""
    mm = create_attachment(s, data=PNG, filename="x.png", uploaded_by=user, kind=kind, media_type="IMAGE", case=case, task=task,
                           latitude=lat, longitude=lng, accuracy_m=5, captured_at=now())
    if case is not None:
        wf.attach_media(s, case, [mm.id], user, kind=kind)
    return mm
