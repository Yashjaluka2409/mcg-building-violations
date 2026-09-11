"""In-app notifications to officers (push to the mobile app is delivered by the platform's FCM service)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.building_violations import Notification, OfficerProfile, ViolationCase


def notify_user(db: Session, user, case: ViolationCase | None, title: str, body: str = "", level: str = "INFO"):
    if user is None:
        return
    db.add(Notification(user_id=user.id, case_id=case.id if case is not None else None, title=title[:200], body=body or "", level=level))
    db.flush()


def notify_role(db: Session, role: str, case: ViolationCase | None, title: str, body: str = "", zone=None, level: str = "INFO"):
    for p in db.query(OfficerProfile).filter(OfficerProfile.role == role, OfficerProfile.active == True).order_by(OfficerProfile.id):  # noqa: E712
        if zone is not None and p.zones and zone.id not in {z.id for z in p.zones}:
            continue
        db.add(Notification(user_id=p.user_id, case_id=case.id if case is not None else None, title=title[:200], body=body or "", level=level))
    db.flush()
