"""Hash-chained audit trail. Every workflow action calls `record_event`.

The chain works like a ledger: each event stores the hash of the previous event of the same
case and its own hash. `verify_chain(case)` recomputes the chain and reports the first break.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.timeutil import now
from app.models.building_violations import CaseEvent, ViolationCase
from app.db.util import client_ip, device_id_of, jsonable


def _role_of(user):
    prof = getattr(user, "bvms_profile", None) if user else None
    return prof.role if prof else ""


def record_event(db: Session, case: ViolationCase, action: str, actor=None, from_status: str = "", to_status: str = "",
                 remarks: str = "", payload: dict | None = None, request=None, lat=None, lng=None) -> CaseEvent:
    last = (db.query(CaseEvent).filter(CaseEvent.case_id == case.id).order_by(CaseEvent.at.desc(), CaseEvent.id.desc()).with_for_update().first())
    ev = CaseEvent(
        case_id=case.id, case=case, at=now(), actor_id=getattr(actor, "id", None), actor_role=_role_of(actor), action=action,
        from_status=from_status or "", to_status=to_status or "", remarks=remarks or "", payload=jsonable(payload or {}),
        prev_hash=last.hash if last else "", ip_address=client_ip(request), device_id=device_id_of(request)[:120],
        latitude=lat, longitude=lng,
    )
    ev.hash = ev.compute_hash()
    db.add(ev)
    db.flush()
    return ev


def verify_chain(db: Session, case: ViolationCase) -> dict:
    prev = ""
    events = db.query(CaseEvent).filter(CaseEvent.case_id == case.id).order_by(CaseEvent.at, CaseEvent.id).all()
    for ev in events:
        if ev.prev_hash != prev or ev.compute_hash() != ev.hash:
            return {"ok": False, "broken_at_event_id": ev.id}
        prev = ev.hash
    return {"ok": True, "events": len(events)}
