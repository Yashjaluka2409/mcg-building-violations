"""Registers and reports with CSV / XLSX export (?export=csv|xlsx, default JSON)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from app.routers.building_violations._router import SyncRouter
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.core.timeutil import now
from app.models import building_violations as m
from app.services.building_violations import hierarchy as H
from app.services.building_violations.location_integrity import explain
from app.core.http import csv_response, resp, xlsx_response
from app.routers.building_violations.deps import DB, Officer, check_perm
from app.repositories.building_violations import dashboard_criteria

router = SyncRouter(prefix="/reports")
C = m.ViolationCase
REPORTS = {}


def report(name):
    def deco(fn):
        REPORTS[name] = fn
        return fn
    return deco


def _name(u):
    p = getattr(u, "bvms_profile", None)
    return p.display_name if p else (u.username if u else "")


def _cases(db, crit, *opts):
    q = db.query(C).filter(*crit)
    return q.options(*opts) if opts else q


@report("case-register")
def case_register(db, crit, params):
    cols = ["case_no", "status", "priority", "land_type", "zone", "ward", "pid", "address", "owner", "violations", "reported_by", "inspected_at", "submitted_at", "scn_issued_at", "scn_served_at",
            "response_due_at", "response_received_at", "decided_at", "decision", "order_issued_at", "order_served_at", "compliance_due_at", "executed_at", "closed_at", "sla_breached", "stop_work", "sealed"]
    rows = []
    for c in _cases(db, crit, selectinload(C.violations)).order_by(C.created_at.desc()):
        rows.append([c.case_no, c.status, c.priority, c.land_type, c.zone.code if c.zone else "", c.ward.number if c.ward else "", c.pid, c.address_line, c.owner_name,
                     "; ".join(v.violation_type_id for v in c.violations), _name(c.reported_by), c.inspected_at, c.submitted_at, c.scn_issued_at, c.scn_served_at, c.response_due_at,
                     c.response_received_at, c.decided_at, c.decision, c.order_issued_at, c.order_served_at, c.compliance_due_at, c.executed_at, c.closed_at, c.sla_breached, c.stop_work_issued, c.sealed])
    return cols, rows


@report("notice-register")
def notice_register(db, crit, params):
    cols = ["notice_no", "kind", "order_type", "statute", "section", "case_no", "pid", "address", "addressee", "mobiles", "issued_by", "issued_at", "response_due_at", "compliance_due_at",
            "served_at", "served_mode", "signature_status", "sms_status", "verification_code"]
    rows = []
    for n in db.query(m.Notice).join(C, m.Notice.case_id == C.id).filter(*crit).order_by(m.Notice.issued_at.desc()).options(selectinload(m.Notice.dispatches)):
        sms = ",".join(f"{d.to}:{d.status}" for d in n.dispatches)
        rows.append([n.notice_no, n.kind, n.order_type.code, n.order_type.statute, n.order_type.section, n.case.case_no, n.case.pid, n.case.address_line, n.addressee_name, ",".join(n.addressee_mobiles),
                     _name(n.issued_by), n.issued_at, n.response_due_at, n.compliance_due_at, n.served_at, n.served_mode, n.signature_status, sms, n.verification_code])
    return cols, rows


@report("order-register")
def order_register(db, crit, params):
    cols, rows = notice_register(db, crit + [C.notices.any(m.Notice.is_final_order == True)], params)  # noqa: E712
    return cols, [r for r in rows if r[1] == "ORDER"]


@report("execution-register")
def execution_register(db, crit, params):
    cols = ["case_no", "address", "ward", "action", "mode", "executed_on", "order_no", "squad_incharge", "police_assistance", "police_station", "duty_magistrate", "area_demolished_sqm", "seal_memo_no", "cost_incurred_inr", "recovery_status", "verified_by", "verified_at"]
    rows = []
    for e in db.query(m.ExecutionRecord).join(C, m.ExecutionRecord.case_id == C.id).filter(*crit).order_by(m.ExecutionRecord.executed_on.desc()):
        rows.append([e.case.case_no, e.case.address_line, e.case.ward.number if e.case.ward else "", e.action, e.mode, e.executed_on, e.order.notice_no if e.order else "", e.squad_incharge, e.police_assistance,
                     e.police_station, e.duty_magistrate, e.area_demolished_sqm, e.seal_memo_no, e.cost_incurred_inr, e.case.cost_recovery_status, _name(e.verified_by), e.verified_at])
    return cols, rows


@report("pendency")
def pendency(db, crit, params):
    t = now()
    cols = ["case_no", "status", "current_owner_role", "owner_name_officer", "zone", "ward", "address", "days_in_stage", "stage_due_at", "overdue_days", "sla_breached"]
    rows = []
    for c in _cases(db, crit).filter(C.status.notin_(["CLOSED", "DROPPED", "REGULARISED"])).order_by(C.stage_due_at):
        owner = {"REPORTER": c.reported_by, "REVIEWER": c.assigned_ae, "AUTHORITY": c.assigned_jc}.get(H.slot_of_role(db, c.current_owner_role) or "")
        overdue = (t - c.stage_due_at).days if c.stage_due_at and c.stage_due_at < t else 0
        rows.append([c.case_no, c.status, c.current_owner_role, _name(owner), c.zone.code if c.zone else "", c.ward.number if c.ward else "", c.address_line, (t - c.status_changed_at).days, c.stage_due_at, overdue, c.sla_breached])
    return cols, rows


@report("govt-land")
def govt_land(db, crit, params):
    cols = ["case_no", "status", "land_type", "agency", "parcel", "khasra", "village", "ward", "address", "occupier", "scn_issued_at", "order_issued_at", "executed_at", "collector_referral"]
    rows = []
    for c in _cases(db, crit).filter(C.land_type.in_(["GOVT_MCG", "GOVT_STATE"])).order_by(C.created_at.desc()):
        ref = next((n for n in c.notices if n.order_type_id == "REFERRAL_TO_COLLECTOR_HPPA"), None)
        p = c.govt_parcel
        rows.append([c.case_no, c.status, c.land_type, p.agency if p else "", p.name if p else "", p.khasra_no if p else "", p.village if p else "", c.ward.number if c.ward else "", c.address_line, c.owner_name or c.occupier_name,
                     c.scn_issued_at, c.order_issued_at, c.executed_at, ref.notice_no if ref else ""])
    return cols, rows


@report("sla-breach")
def sla_breach(db, crit, params):
    cols = ["case_no", "status", "current_owner_role", "zone", "ward", "stage_due_at", "breached_at", "escalated_to"]
    rows = []
    for ev in db.query(m.CaseEvent).join(C, m.CaseEvent.case_id == C.id).filter(*crit, m.CaseEvent.action == "SLA_BREACH").order_by(m.CaseEvent.at.desc()):
        c = ev.case
        rows.append([c.case_no, ev.to_status, c.current_owner_role, c.zone.code if c.zone else "", c.ward.number if c.ward else "", c.stage_due_at, ev.at, ev.remarks.split("escalated to ")[-1]])
    return cols, rows


@report("litigation-register")
def litigation_register(db, crit, params):
    cols = ["case_no", "case_status", "address", "ward", "authority", "appeal_no", "appellant", "filed_on", "order_appealed", "appeal_status", "stay", "stay_order_date", "stay_until", "stay_scope", "stay_order_uploaded", "next_hearing_on", "counsel_for_mcg", "decided_on", "decision"]
    rows = []
    for a in db.query(m.Appeal).join(C, m.Appeal.case_id == C.id).filter(*crit).order_by(m.Appeal.filed_on.desc(), m.Appeal.id.desc()):
        c = a.case
        rows.append([c.case_no, c.status, c.address_line, c.ward.number if c.ward else "", a.get_authority_display(), a.appeal_no, a.appellant_name, a.filed_on, a.order.notice_no if a.order else "", a.status, a.stay_granted, a.stay_order_date, a.stay_until, a.stay_scope, bool(a.stay_order_id), a.next_hearing_on, a.counsel_for_mcg, a.decided_on, a.decision_summary])
    return cols, rows


@report("branch-referrals")
def branch_referrals(db, crit, params):
    cols = ["case_no", "case_status", "address", "branch", "referred_by", "referred_on", "query", "due_on", "hold_case", "status", "responded_on", "responded_by", "recommendation", "response"]
    rows = []
    for r in db.query(m.BranchReferral).join(C, m.BranchReferral.case_id == C.id).filter(*crit).order_by(m.BranchReferral.referred_at.desc()):
        rows.append([r.case.case_no, r.case.status, r.case.address_line, r.branch.name_en, _name(r.referred_by), r.referred_at, r.query, r.due_at, r.hold_case, r.status, r.responded_at, _name(r.responded_by), r.recommendation, r.response])
    return cols, rows


@report("location-integrity")
def location_integrity(db, crit, params):
    """Every location-integrity check (accepted, flagged and rejected). Rejected rows are spoofing incidents."""
    cols = ["at", "officer", "role", "context", "decision", "reasons", "flags", "explanation", "case_no", "task_id", "platform", "source", "app_version",
            "device_model", "os_version", "device_id", "latitude", "longitude", "accuracy_m", "fix_age_s", "native_module", "mock_location", "rooted",
            "emulator", "developer_options", "vpn_active", "proxy_configured", "simulated_by_software", "attestation_status", "client_ip",
            "ip_vpn_or_proxy", "ip_distance_km", "travel_distance_km", "travel_speed_kmph"]
    rows = []
    L = m.LocationIntegrityCheck
    scoped_case_ids = db.query(C.id).filter(*crit)
    checks = db.query(L).filter(or_(L.case_id.in_(scoped_case_ids), L.case_id.is_(None)))
    if params.get("decision"):
        checks = checks.filter(L.decision == params["decision"])
    for c in checks.order_by(L.at.desc()).limit(5000):
        prof = getattr(c.officer, "bvms_profile", None)
        rows.append([c.at, _name(c.officer), prof.role if prof else "", c.get_context_display(), c.decision, "; ".join(c.reasons), "; ".join(c.flags),
                     explain(list(c.reasons) + list(c.flags)), c.case.case_no if c.case else "", c.task_id or "", c.platform, c.source, c.app_version,
                     c.device_model, c.os_version, c.device_id, c.latitude, c.longitude, c.accuracy_m, c.fix_age_s, c.native_module, c.mock_location, c.rooted,
                     (c.is_physical_device is False) if c.is_physical_device is not None else None, c.developer_options, c.vpn_active, c.proxy_configured,
                     c.simulated_by_software, c.attestation_status, c.client_ip, (c.ip_intel or {}).get("privacy"), c.ip_distance_km, c.travel_distance_km, c.travel_speed_kmph])
    return cols, rows


@report("legacy-orders")
def legacy_orders(db, crit, params):
    """Orders issued on paper before the system, with their current status (services/legacy.py)."""
    cols = ["case_no", "order_no", "order_type", "order_date", "signatory", "pid", "address", "ward", "owner", "served_on", "served_mode", "compliance_due",
            "status", "executed_on", "execution_action", "appeal_authority", "stay_until", "closed_on", "legacy_reference", "batch", "recorded_by", "recorded_at"]
    rows = []
    for c in _cases(db, crit).filter(C.source == "LEGACY_ORDER").order_by(C.order_issued_at.desc()):
        n = c.final_order
        ex = c.executions[0] if c.executions else None
        ap = c.appeals[0] if c.appeals else None
        rows.append([c.case_no, n.notice_no if n else "", n.order_type_id if n else "", n.issued_at.date() if n else "", n.signer_name if n else "", c.pid, c.address_line,
                     c.ward.number if c.ward else "", c.owner_name, c.order_served_at.date() if c.order_served_at else "", n.served_mode if n else "",
                     c.compliance_due_at.date() if c.compliance_due_at else "", c.status, c.executed_at.date() if c.executed_at else "", ex.action if ex else "",
                     ap.get_authority_display() if ap else "", c.stay_until, c.closed_at.date() if c.closed_at else "", c.legacy_reference,
                     c.legacy_batch.title if c.legacy_batch else "", _name(c.reported_by), c.created_at])
    return cols, rows


@report("planned-inspections")
def planned_inspections(db, crit, params):
    cols = ["task_id", "batch", "category", "pid", "address", "ward", "assigned_to", "assigned_at", "due_at", "status", "started_at", "start_distance_m", "completed_at", "case_no", "outcome_remarks", "created_by"]
    rows = []
    for t in db.query(m.InspectionTask).order_by(m.InspectionTask.id):
        c = t.case
        rows.append([t.id, t.batch.title if t.batch else "", t.category, t.pid, t.address, t.ward.number if t.ward else "", _name(t.assigned_to), t.assigned_at, t.due_at, t.status, t.started_at, t.start_distance_m, t.completed_at, c.case_no if c else "", t.outcome_remarks, _name(t.created_by)])
    return cols, rows


@report("sanctioned-plans")
def sanctioned_plans(db, crit, params):
    cols = ["plan_no", "pid", "address", "ward", "owner", "mobile", "land_use", "sanctioned_on", "valid_till", "permitted_floors", "licence_no", "licence_holder", "licence_authority", "status", "cases"]
    rows = []
    for p in db.query(m.SanctionedPlan).order_by(m.SanctionedPlan.id):
        rows.append([p.plan_no, p.pid, p.address, p.ward.number if p.ward else "", p.owner_name, p.owner_mobile, p.land_use, p.sanctioned_on, p.valid_till, p.permitted_floors, p.licence_no, p.licence_holder, p.licence_authority, p.status, "; ".join(c.case_no for c in p.cases)])
    return cols, rows


@router.get("/")
def report_list(user: Officer):
    return resp([{"name": n, "title": n.replace("-", " ").title()} for n in REPORTS])


@router.get("/{name}/")
def run_report(name: str, request: Request, user: Officer, db: DB):
    check_perm(db, user, "REPORTS_EXPORT")
    fn = REPORTS.get(name)
    if not fn:
        return resp({"detail": f"Unknown report. Available: {', '.join(REPORTS)}"}, 404)
    crit = dashboard_criteria(db, user, request.query_params)
    cols, rows = fn(db, crit, request.query_params)
    fmt = request.query_params.get("export", "json")
    if fmt == "csv":
        return csv_response(f"{name}.csv", cols, rows)
    if fmt == "xlsx":
        return xlsx_response(f"{name}.xlsx", name, cols, rows)
    return resp({"columns": cols, "rows": rows, "count": len(rows)})
