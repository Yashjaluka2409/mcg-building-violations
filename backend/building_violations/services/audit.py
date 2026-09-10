"""Hash-chained audit trail. Every workflow action calls `record_event`.

The chain works like a ledger: each event stores the hash of the previous event of the same
case and its own hash. `verify_chain(case)` recomputes the chain and reports the first break.
"""
from __future__ import annotations

from django.db import transaction

from ..models import CaseEvent, ViolationCase


def _role_of(user):
    prof = getattr(user, "bvms_profile", None) if user else None
    return prof.role if prof else ""


def record_event(case: ViolationCase, action: str, actor=None, from_status: str = "", to_status: str = "",
                 remarks: str = "", payload: dict | None = None, request=None, lat=None, lng=None) -> CaseEvent:
    with transaction.atomic():
        last = CaseEvent.objects.select_for_update().filter(case=case).order_by("-at", "-id").first()
        ev = CaseEvent(
            case=case, actor=actor if getattr(actor, "pk", None) else None, actor_role=_role_of(actor), action=action,
            from_status=from_status, to_status=to_status, remarks=remarks or "", payload=payload or {},
            prev_hash=last.hash if last else "",
            ip_address=_client_ip(request), device_id=(request.headers.get("X-Device-Id", "") if request else ""),
            latitude=lat, longitude=lng,
        )
        ev.hash = ev.compute_hash()
        ev.save()
        return ev


def verify_chain(case: ViolationCase) -> dict:
    prev = ""
    for ev in case.events.order_by("at", "id"):
        if ev.prev_hash != prev or ev.compute_hash() != ev.hash:
            return {"ok": False, "broken_at_event_id": ev.id}
        prev = ev.hash
    return {"ok": True, "events": case.events.count()}


def _client_ip(request):
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")) or None
