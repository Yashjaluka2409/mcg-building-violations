"""Registers and reports with CSV / XLSX export (?export=csv|xlsx, default JSON).
(`export` rather than `format`, because DRF reserves ?format= for its own renderers.)"""
import csv
import io

from django.db import models
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import models as m
from .permissions import HasOfficerProfile, HasPerm
from .views_dashboards import _scoped

REPORTS = {}


def report(name):
    def deco(fn):
        REPORTS[name] = fn
        return fn
    return deco


def _name(u):
    p = getattr(u, "bvms_profile", None)
    return p.display_name if p else (u.get_username() if u else "")


@report("case-register")
def case_register(qs, params):
    cols = ["case_no", "status", "priority", "land_type", "zone", "ward", "pid", "address", "owner", "violations", "reported_by", "inspected_at", "submitted_at", "scn_issued_at", "scn_served_at",
            "response_due_at", "response_received_at", "decided_at", "decision", "order_issued_at", "order_served_at", "compliance_due_at", "executed_at", "closed_at", "sla_breached", "stop_work", "sealed"]
    rows = []
    for c in qs.select_related("zone", "ward", "reported_by").prefetch_related("violations__violation_type"):
        rows.append([c.case_no, c.status, c.priority, c.land_type, c.zone.code if c.zone else "", c.ward.number if c.ward else "", c.pid, c.address_line, c.owner_name,
                     "; ".join(v.violation_type_id for v in c.violations.all()), _name(c.reported_by), c.inspected_at, c.submitted_at, c.scn_issued_at, c.scn_served_at, c.response_due_at,
                     c.response_received_at, c.decided_at, c.decision, c.order_issued_at, c.order_served_at, c.compliance_due_at, c.executed_at, c.closed_at, c.sla_breached, c.stop_work_issued, c.sealed])
    return cols, rows


@report("notice-register")
def notice_register(qs, params):
    cols = ["notice_no", "kind", "order_type", "statute", "section", "case_no", "pid", "address", "addressee", "mobiles", "issued_by", "issued_at", "response_due_at", "compliance_due_at",
            "served_at", "served_mode", "signature_status", "sms_status", "verification_code"]
    rows = []
    for n in m.Notice.objects.filter(case__in=qs).select_related("case", "order_type", "issued_by").prefetch_related("dispatches"):
        sms = ",".join(f"{d.to}:{d.status}" for d in n.dispatches.all())
        rows.append([n.notice_no, n.kind, n.order_type.code, n.order_type.statute, n.order_type.section, n.case.case_no, n.case.pid, n.case.address_line, n.addressee_name, ",".join(n.addressee_mobiles),
                     _name(n.issued_by), n.issued_at, n.response_due_at, n.compliance_due_at, n.served_at, n.served_mode, n.signature_status, sms, n.verification_code])
    return cols, rows


@report("order-register")
def order_register(qs, params):
    cols, rows = notice_register(qs.filter(notices__is_final_order=True).distinct(), params)
    return cols, [r for r in rows if r[1] == "ORDER"]


@report("execution-register")
def execution_register(qs, params):
    cols = ["case_no", "address", "ward", "action", "mode", "executed_on", "order_no", "squad_incharge", "police_assistance", "police_station", "duty_magistrate", "area_demolished_sqm", "seal_memo_no", "cost_incurred_inr", "recovery_status", "verified_by", "verified_at"]
    rows = []
    for e in m.ExecutionRecord.objects.filter(case__in=qs).select_related("case", "case__ward", "order", "verified_by"):
        rows.append([e.case.case_no, e.case.address_line, e.case.ward.number if e.case.ward else "", e.action, e.mode, e.executed_on, e.order.notice_no if e.order else "", e.squad_incharge, e.police_assistance,
                     e.police_station, e.duty_magistrate, e.area_demolished_sqm, e.seal_memo_no, e.cost_incurred_inr, e.case.cost_recovery_status, _name(e.verified_by), e.verified_at])
    return cols, rows


@report("pendency")
def pendency(qs, params):
    from django.utils import timezone
    now = timezone.now()
    cols = ["case_no", "status", "current_owner_role", "owner_name_officer", "zone", "ward", "address", "days_in_stage", "stage_due_at", "overdue_days", "sla_breached"]
    rows = []
    for c in qs.exclude(status__in=["CLOSED", "DROPPED", "REGULARISED"]).select_related("zone", "ward", "reported_by", "assigned_ae", "assigned_jc"):
        owner = {"JE": c.reported_by, "AE": c.assigned_ae, "JC": c.assigned_jc}.get(c.current_owner_role)
        overdue = (now - c.stage_due_at).days if c.stage_due_at and c.stage_due_at < now else 0
        rows.append([c.case_no, c.status, c.current_owner_role, _name(owner), c.zone.code if c.zone else "", c.ward.number if c.ward else "", c.address_line, (now - c.status_changed_at).days, c.stage_due_at, overdue, c.sla_breached])
    return cols, rows


@report("govt-land")
def govt_land(qs, params):
    cols = ["case_no", "status", "land_type", "agency", "parcel", "khasra", "village", "ward", "address", "occupier", "scn_issued_at", "order_issued_at", "executed_at", "collector_referral"]
    rows = []
    for c in qs.filter(land_type__in=["GOVT_MCG", "GOVT_STATE"]).select_related("govt_parcel", "ward"):
        ref = c.notices.filter(order_type__code="REFERRAL_TO_COLLECTOR_HPPA").first()
        p = c.govt_parcel
        rows.append([c.case_no, c.status, c.land_type, p.agency if p else "", p.name if p else "", p.khasra_no if p else "", p.village if p else "", c.ward.number if c.ward else "", c.address_line, c.owner_name or c.occupier_name,
                     c.scn_issued_at, c.order_issued_at, c.executed_at, ref.notice_no if ref else ""])
    return cols, rows


@report("sla-breach")
def sla_breach(qs, params):
    cols = ["case_no", "status", "current_owner_role", "zone", "ward", "stage_due_at", "breached_at", "escalated_to"]
    rows = []
    for ev in m.CaseEvent.objects.filter(case__in=qs, action="SLA_BREACH").select_related("case", "case__zone", "case__ward"):
        c = ev.case
        rows.append([c.case_no, ev.to_status, c.current_owner_role, c.zone.code if c.zone else "", c.ward.number if c.ward else "", c.stage_due_at, ev.at, ev.remarks.split("escalated to ")[-1]])
    return cols, rows


@report("litigation-register")
def litigation_register(qs, params):
    cols = ["case_no", "case_status", "address", "ward", "authority", "appeal_no", "appellant", "filed_on", "order_appealed", "appeal_status", "stay", "stay_order_date", "stay_until", "stay_scope", "stay_order_uploaded", "next_hearing_on", "counsel_for_mcg", "decided_on", "decision"]
    rows = []
    for a in m.Appeal.objects.filter(case__in=qs).select_related("case", "case__ward", "order", "stay_order"):
        c = a.case
        rows.append([c.case_no, c.status, c.address_line, c.ward.number if c.ward else "", a.get_authority_display(), a.appeal_no, a.appellant_name, a.filed_on, a.order.notice_no if a.order else "", a.status, a.stay_granted, a.stay_order_date, a.stay_until, a.stay_scope, bool(a.stay_order_id), a.next_hearing_on, a.counsel_for_mcg, a.decided_on, a.decision_summary])
    return cols, rows


@report("branch-referrals")
def branch_referrals(qs, params):
    cols = ["case_no", "case_status", "address", "branch", "referred_by", "referred_on", "query", "due_on", "hold_case", "status", "responded_on", "responded_by", "recommendation", "response"]
    rows = []
    for r in m.BranchReferral.objects.filter(case__in=qs).select_related("case", "branch", "referred_by", "responded_by"):
        rows.append([r.case.case_no, r.case.status, r.case.address_line, r.branch.name_en, _name(r.referred_by), r.referred_at, r.query, r.due_at, r.hold_case, r.status, r.responded_at, _name(r.responded_by), r.recommendation, r.response])
    return cols, rows


@report("location-integrity")
def location_integrity(qs, params):
    """Every location-integrity check (accepted, flagged and rejected). Rejected rows are spoofing incidents."""
    from ..services.location_integrity import explain
    cols = ["at", "officer", "role", "context", "decision", "reasons", "flags", "explanation", "case_no", "task_id", "platform", "source", "app_version",
            "device_model", "os_version", "device_id", "latitude", "longitude", "accuracy_m", "fix_age_s", "native_module", "mock_location", "rooted",
            "emulator", "developer_options", "vpn_active", "proxy_configured", "simulated_by_software", "attestation_status", "client_ip",
            "ip_vpn_or_proxy", "ip_distance_km", "travel_distance_km", "travel_speed_kmph"]
    rows = []
    checks = m.LocationIntegrityCheck.objects.select_related("officer__bvms_profile", "case", "task").filter(
        models.Q(case__in=qs) | models.Q(case__isnull=True))
    if params.get("decision"):
        checks = checks.filter(decision=params["decision"])
    for c in checks[:5000]:
        prof = getattr(c.officer, "bvms_profile", None)
        rows.append([c.at, _name(c.officer), prof.role if prof else "", c.get_context_display(), c.decision, "; ".join(c.reasons), "; ".join(c.flags),
                     explain(list(c.reasons) + list(c.flags)), c.case.case_no if c.case else "", c.task_id or "", c.platform, c.source, c.app_version,
                     c.device_model, c.os_version, c.device_id, c.latitude, c.longitude, c.accuracy_m, c.fix_age_s, c.native_module, c.mock_location, c.rooted,
                     (c.is_physical_device is False) if c.is_physical_device is not None else None, c.developer_options, c.vpn_active, c.proxy_configured,
                     c.simulated_by_software, c.attestation_status, c.client_ip, (c.ip_intel or {}).get("privacy"), c.ip_distance_km, c.travel_distance_km, c.travel_speed_kmph])
    return cols, rows


@report("legacy-orders")
def legacy_orders(qs, params):
    """Orders issued on paper before the system, with their current status (services/legacy.py)."""
    cols = ["case_no", "order_no", "order_type", "order_date", "signatory", "pid", "address", "ward", "owner", "served_on", "served_mode", "compliance_due",
            "status", "executed_on", "execution_action", "appeal_authority", "stay_until", "closed_on", "legacy_reference", "batch", "recorded_by", "recorded_at"]
    rows = []
    for c in qs.filter(source="LEGACY_ORDER").select_related("final_order__order_type", "ward", "reported_by", "legacy_batch").prefetch_related("executions", "appeals"):
        n = c.final_order
        ex = c.executions.order_by("-executed_on").first()
        ap = c.appeals.order_by("-filed_on").first()
        rows.append([c.case_no, n.notice_no if n else "", n.order_type_id if n else "", n.issued_at.date() if n else "", n.signer_name if n else "", c.pid, c.address_line,
                     c.ward.number if c.ward else "", c.owner_name, c.order_served_at.date() if c.order_served_at else "", n.served_mode if n else "",
                     c.compliance_due_at.date() if c.compliance_due_at else "", c.status, c.executed_at.date() if c.executed_at else "", ex.action if ex else "",
                     ap.get_authority_display() if ap else "", c.stay_until, c.closed_at.date() if c.closed_at else "", c.legacy_reference,
                     c.legacy_batch.title if c.legacy_batch else "", _name(c.reported_by), c.created_at])
    return cols, rows


@report("planned-inspections")
def planned_inspections(qs, params):
    cols = ["task_id", "batch", "category", "pid", "address", "ward", "assigned_to", "assigned_at", "due_at", "status", "started_at", "start_distance_m", "completed_at", "case_no", "outcome_remarks", "created_by"]
    rows = []
    for t in m.InspectionTask.objects.select_related("batch", "ward", "assigned_to", "created_by").prefetch_related("case"):
        c = getattr(t, "case", None)
        rows.append([t.id, t.batch.title if t.batch else "", t.category, t.pid, t.address, t.ward.number if t.ward else "", _name(t.assigned_to), t.assigned_at, t.due_at, t.status, t.started_at, t.start_distance_m, t.completed_at, c.case_no if c else "", t.outcome_remarks, _name(t.created_by)])
    return cols, rows


@report("sanctioned-plans")
def sanctioned_plans(qs, params):
    cols = ["plan_no", "pid", "address", "ward", "owner", "mobile", "land_use", "sanctioned_on", "valid_till", "permitted_floors", "licence_no", "licence_holder", "licence_authority", "status", "cases"]
    rows = []
    for p in m.SanctionedPlan.objects.select_related("ward").prefetch_related("cases"):
        rows.append([p.plan_no, p.pid, p.address, p.ward.number if p.ward else "", p.owner_name, p.owner_mobile, p.land_use, p.sanctioned_on, p.valid_till, p.permitted_floors, p.licence_no, p.licence_holder, p.licence_authority, p.status, "; ".join(c.case_no for c in p.cases.all())])
    return cols, rows


class ReportView(APIView):
    permission_classes = [HasPerm.of("REPORTS_EXPORT")]

    def get(self, request, name):
        fn = REPORTS.get(name)
        if not fn:
            return Response({"detail": f"Unknown report. Available: {', '.join(REPORTS)}"}, status=404)
        qs = _scoped(request)
        cols, rows = fn(qs, request.query_params)
        fmt = request.query_params.get("export", "json")
        if fmt == "csv":
            resp = HttpResponse(content_type="text/csv")
            resp["Content-Disposition"] = f'attachment; filename="{name}.csv"'
            w = csv.writer(resp)
            w.writerow(cols)
            for r in rows:
                w.writerow(["" if v is None else v for v in r])
            return resp
        if fmt == "xlsx":
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = name[:30]
            ws.append(cols)
            for r in rows:
                ws.append([v.replace(tzinfo=None) if hasattr(v, "tzinfo") and v.tzinfo else v for v in r])
            buf = io.BytesIO()
            wb.save(buf)
            resp = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            resp["Content-Disposition"] = f'attachment; filename="{name}.xlsx"'
            return resp
        return Response({"columns": cols, "rows": rows, "count": len(rows)})

    @staticmethod
    def available():
        return list(REPORTS)


class ReportListView(APIView):
    permission_classes = [HasOfficerProfile]

    def get(self, request):
        return Response([{"name": n, "title": n.replace("-", " ").title()} for n in REPORTS])
