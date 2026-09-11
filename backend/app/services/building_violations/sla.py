"""SLA computation and escalation."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.timeutil import now
from app.models.building_violations import CaseStatus, Notification, OfficerProfile, Role, SLAConfig, ViolationCase

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


def stage_due(db: Session, status: str, from_dt=None):
    from_dt = from_dt or now()
    cfg = db.query(SLAConfig).filter(SLAConfig.stage == status, SLAConfig.active == True).first()  # noqa: E712
    hours = cfg.hours if cfg else DEFAULT_SLA_HOURS.get(status)
    return (from_dt + timedelta(hours=hours)) if hours else None


def escalation_role(db: Session, status: str):
    cfg = db.query(SLAConfig).filter(SLAConfig.stage == status, SLAConfig.active == True).first()  # noqa: E712
    return (cfg.escalate_to_role if cfg and cfg.escalate_to_role else DEFAULT_ESCALATION.get(status)) or ""


def escalate(db: Session, case: ViolationCase):
    """Mark breach and notify the escalation role for the case's zone (idempotent per stage)."""
    from app.services.building_violations.audit import record_event
    if case.sla_breached:
        return
    case.sla_breached = True
    db.flush()
    role = escalation_role(db, case.status)
    record_event(db, case, "SLA_BREACH", to_status=case.status, remarks=f"Stage SLA breached; escalated to {role or 'none'}")
    if not role:
        return
    for p in db.query(OfficerProfile).filter(OfficerProfile.role == role, OfficerProfile.active == True).order_by(OfficerProfile.id):  # noqa: E712
        if case.zone_id and p.zones and case.zone_id not in {z.id for z in p.zones}:
            continue
        db.add(Notification(user_id=p.user_id, case_id=case.id, level="ESCALATION", title=f"SLA breached: {case.case_no}",
                            body=f"Case {case.case_no} has been in stage {case.get_status_display()} beyond the SLA. Owner: {case.current_owner_role}."))
    db.flush()
