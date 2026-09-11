"""SLA computation and escalation."""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from ..models import CaseStatus, Notification, OfficerProfile, Role, SLAConfig, ViolationCase

DEFAULT_SLA_HOURS = {
    CaseStatus.PENDING_AE: 72,
    CaseStatus.RETURNED_TO_JE: 72,
    CaseStatus.PENDING_JC: 120,
    CaseStatus.SCN_ISSUED: 72,          # time for the field team to serve the notice
    CaseStatus.RESPONSE_RECEIVED: 120,  # JC decision after response
    CaseStatus.RESPONSE_PENDING_AE: 48,
    CaseStatus.RESPONSE_PENDING_JC: 120,
    CaseStatus.NO_RESPONSE: 120,
    CaseStatus.HEARING_SCHEDULED: 240,
    CaseStatus.ORDER_ISSUED: 72,        # serve the order
    CaseStatus.EXECUTION_DUE: 168,      # execute within a week of the period expiring
    CaseStatus.EXECUTED: 72,            # close after verification
}
DEFAULT_ESCALATION = {
    CaseStatus.PENDING_AE: Role.XEN, CaseStatus.RETURNED_TO_JE: Role.AE, CaseStatus.PENDING_JC: Role.ADDL_COMMISSIONER,
    CaseStatus.SCN_ISSUED: Role.AE, CaseStatus.ORDER_ISSUED: Role.AE, CaseStatus.EXECUTION_DUE: Role.JC,
    CaseStatus.RESPONSE_RECEIVED: Role.ADDL_COMMISSIONER, CaseStatus.RESPONSE_PENDING_JC: Role.ADDL_COMMISSIONER,
    CaseStatus.NO_RESPONSE: Role.ADDL_COMMISSIONER,
}


def stage_due(status: str, from_dt=None):
    from_dt = from_dt or timezone.now()
    cfg = SLAConfig.objects.filter(stage=status, active=True).first()
    hours = cfg.hours if cfg else DEFAULT_SLA_HOURS.get(status)
    return (from_dt + timedelta(hours=hours)) if hours else None


def escalation_role(status: str):
    cfg = SLAConfig.objects.filter(stage=status, active=True).first()
    return (cfg.escalate_to_role if cfg and cfg.escalate_to_role else DEFAULT_ESCALATION.get(status)) or ""


def escalate(case: ViolationCase):
    """Mark breach and notify the escalation role for the case's zone (idempotent per stage)."""
    from .audit import record_event
    if case.sla_breached:
        return
    case.sla_breached = True
    case.save(update_fields=["sla_breached"])
    role = escalation_role(case.status)
    record_event(case, "SLA_BREACH", to_status=case.status, remarks=f"Stage SLA breached; escalated to {role or 'none'}")
    if not role:
        return
    profiles = OfficerProfile.objects.filter(role=role, active=True)
    if case.zone_id:
        profiles = profiles.filter(zones=case.zone) | profiles.filter(zones__isnull=True)
    for p in profiles.distinct():
        Notification.objects.create(user=p.user, case=case, level="ESCALATION",
                                    title=f"SLA breached: {case.case_no}",
                                    body=f"Case {case.case_no} has been in stage {case.get_status_display()} beyond the SLA. Owner: {case.current_owner_role}.")
