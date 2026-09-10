"""In-app notifications to officers (push to the mobile app is delivered by the platform's FCM service)."""
from __future__ import annotations

from ..models import Notification, OfficerProfile, Role, ViolationCase


def notify_user(user, case: ViolationCase | None, title: str, body: str = "", level: str = "INFO"):
    if user is None:
        return
    Notification.objects.create(user=user, case=case, title=title, body=body, level=level)


def notify_role(role: str, case: ViolationCase | None, title: str, body: str = "", zone=None, level: str = "INFO"):
    qs = OfficerProfile.objects.filter(role=role, active=True)
    if zone is not None:
        qs = qs.filter(zones=zone) | qs.filter(zones__isnull=True)
    for p in qs.distinct():
        Notification.objects.create(user=p.user, case=case, title=title, body=body, level=level)
