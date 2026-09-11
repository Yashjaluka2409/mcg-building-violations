"""MIS dashboards. All endpoints accept ?zone=&ward=&from=&to= (dates) and honour the user's jurisdiction."""
from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import models as m
from .permissions import HasOfficerProfile, HasPerm
from .views_cases import ViolationCaseViewSet

OPEN_EXCLUDE = ["CLOSED", "DROPPED", "REGULARISED"]
STAGE_ORDER = ["DRAFT", "PENDING_AE", "RETURNED_TO_JE", "PENDING_JC", "SCN_ISSUED", "SCN_SERVED", "RESPONSE_PENDING_AE", "RESPONSE_PENDING_JC", "RESPONSE_RECEIVED", "NO_RESPONSE",
               "HEARING_SCHEDULED", "ORDER_ISSUED", "ORDER_SERVED", "APPEAL_STAY", "EXECUTION_DUE", "COMPLIED", "EXECUTED", "CLOSED", "DROPPED", "REGULARISED"]


def _scoped(request):
    vs = ViolationCaseViewSet()
    vs.request = request
    qs = vs.get_queryset()
    p = request.query_params
    if p.get("zone"):
        qs = qs.filter(zone_id=p["zone"])
    if p.get("ward"):
        qs = qs.filter(ward_id=p["ward"])
    if p.get("land_type"):
        qs = qs.filter(land_type=p["land_type"])
    if p.get("from"):
        qs = qs.filter(created_at__date__gte=p["from"])
    if p.get("to"):
        qs = qs.filter(created_at__date__lte=p["to"])
    return qs


class _Base(APIView):
    permission_classes = [HasPerm.of("DASHBOARD_VIEW")]


class SummaryView(_Base):
    def get(self, request):
        qs = _scoped(request)
        now = timezone.now()
        open_qs = qs.exclude(status__in=OPEN_EXCLUDE)
        notices = m.Notice.objects.filter(case__in=qs)
        execs = m.ExecutionRecord.objects.filter(case__in=qs)
        d30 = now - timedelta(days=30)
        return Response({
            "cases_total": qs.count(), "cases_open": open_qs.count(), "cases_new_30d": qs.filter(created_at__gte=d30).count(),
            "govt_land_cases": qs.filter(land_type__in=["GOVT_MCG", "GOVT_STATE"]).count(),
            "pending_ae": qs.filter(status__in=["PENDING_AE", "RESPONSE_PENDING_AE"]).count(),
            "pending_jc": qs.filter(status__in=["PENDING_JC", "RESPONSE_PENDING_JC", "RESPONSE_RECEIVED", "NO_RESPONSE", "HEARING_SCHEDULED"]).count(),
            "scn_issued": notices.filter(kind="NOTICE").count(), "scn_pending_service": qs.filter(status="SCN_ISSUED").count(),
            "responses_awaited": qs.filter(status="SCN_SERVED").count(), "no_response": qs.filter(status="NO_RESPONSE").count(),
            "stop_work_orders": notices.filter(order_type__code="STOP_WORK_262").count(), "sealing_orders": notices.filter(order_type__code__in=["SEALING_263A", "RESEALING_263A"]).count(),
            "demolition_orders": notices.filter(order_type__code__in=["DEMOLITION_ORDER_261", "EVICTION_DEMOLITION_ORDER_408A", "DEMOLITION_ORDER_284"]).count(),
            "orders_pending_service": qs.filter(status="ORDER_ISSUED").count(), "compliance_running": qs.filter(status="ORDER_SERVED").count(),
            "execution_due": qs.filter(status="EXECUTION_DUE").count(), "stayed": qs.filter(status="APPEAL_STAY").count(),
            "demolished": execs.filter(action__in=["DEMOLITION", "PARTIAL_DEMOLITION"], mode="CORPORATION").count(),
            "sealed": qs.filter(sealed=True).count(), "self_complied": qs.filter(status__in=["COMPLIED"]).count() + execs.filter(mode="OWNER_SELF").count(),
            "closed": qs.filter(status="CLOSED").count(), "dropped": qs.filter(status="DROPPED").count(), "regularised": qs.filter(status="REGULARISED").count(),
            "sla_breached_open": open_qs.filter(sla_breached=True).count(),
            "signature_failed": notices.filter(signature_status="FAILED").count(),
            "sms_failed": m.NoticeDispatch.objects.filter(notice__case__in=qs, status="FAILED").count(),
            "demolition_cost_inr": float(qs.aggregate(t=Sum("demolition_cost_inr"))["t"] or 0),
            "litigation_pending": qs.filter(litigation_status="APPEAL_PENDING").count(),
            "stayed_high_court": qs.filter(litigation_status="STAYED", litigation_authority="HIGH_COURT").count(),
            "stayed_supreme_court": qs.filter(litigation_status="STAYED", litigation_authority="SUPREME_COURT").count(),
            "stayed_divisional_commissioner": qs.filter(litigation_status="STAYED", litigation_authority="DIVISIONAL_COMMISSIONER").count(),
            "stays_expiring_7d": m.Appeal.objects.filter(case__in=qs, status="STAYED", stay_until__isnull=False, stay_until__lte=(now + timedelta(days=7)).date()).count(),
            "referrals_pending": m.BranchReferral.objects.filter(case__in=qs, status="PENDING").count(),
            "tasks_open": m.InspectionTask.objects.filter(status__in=["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"]).count(),
            "tasks_overdue": m.InspectionTask.objects.filter(status__in=["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"], due_at__lt=now).count(),
            "tasks_violation_found": m.InspectionTask.objects.filter(status="VIOLATION_RECORDED").count(),
            "tasks_no_violation": m.InspectionTask.objects.filter(status__in=["NO_VIOLATION", "NOT_FOUND"]).count(),
            "referrals_overdue": m.BranchReferral.objects.filter(case__in=qs, status="PENDING", due_at__lt=now).count(),
            "integrity_rejected_30d": m.LocationIntegrityCheck.objects.filter(decision="REJECTED", at__gte=now - timedelta(days=30)).count(),
            "integrity_flagged_30d": m.LocationIntegrityCheck.objects.filter(decision="FLAGGED", at__gte=now - timedelta(days=30)).count(),
            "integrity_checked_30d": m.LocationIntegrityCheck.objects.filter(at__gte=now - timedelta(days=30)).exclude(context="PRECHECK").count(),
            "cost_recovery_pending": qs.filter(cost_recovery_status__in=["PENDING", "DEMANDED"]).count(),
        })


class StageFunnelView(_Base):
    def get(self, request):
        qs = _scoped(request)
        counts = {r["status"]: r["n"] for r in qs.values("status").annotate(n=Count("id"))}
        return Response([{"status": st, "label": dict(m.CaseStatus.choices).get(st, st), "count": counts.get(st, 0)} for st in STAGE_ORDER])


class ByZoneWardView(_Base):
    def get(self, request):
        qs = _scoped(request)
        by = request.query_params.get("by", "zone")
        key = "ward__number" if by == "ward" else "zone__code"
        rows = (qs.values(key).annotate(total=Count("id"), open=Count("id", filter=~Q(status__in=OPEN_EXCLUDE)), govt=Count("id", filter=Q(land_type__in=["GOVT_MCG", "GOVT_STATE"])),
                                 scn=Count("notices", filter=Q(notices__kind="NOTICE"), distinct=True),
                                 orders=Count("notices", filter=Q(notices__is_final_order=True), distinct=True),
                                 executed=Count("id", filter=Q(status__in=["EXECUTED", "COMPLIED", "CLOSED"])), breached=Count("id", filter=Q(sla_breached=True) & ~Q(status__in=OPEN_EXCLUDE)))
                .order_by(key))
        return Response([{"key": r[key], **{k: v for k, v in r.items() if k != key}} for r in rows])


class ViolationMixView(_Base):
    def get(self, request):
        qs = _scoped(request)
        rows = (m.CaseViolation.objects.filter(case__in=qs).values("violation_type__code", "violation_type__title_en", "violation_type__category")
                .annotate(n=Count("id")).order_by("-n"))
        cats = m.CaseViolation.objects.filter(case__in=qs).values("violation_type__category").annotate(n=Count("id")).order_by("-n")
        return Response({"by_type": [{"code": r["violation_type__code"], "title": r["violation_type__title_en"], "category": r["violation_type__category"], "count": r["n"]} for r in rows],
                         "by_category": [{"category": r["violation_type__category"], "count": r["n"]} for r in cats],
                         "by_land_type": [{"land_type": r["land_type"], "count": r["n"]} for r in qs.values("land_type").annotate(n=Count("id"))]})


class AgeingView(_Base):
    def get(self, request):
        qs = _scoped(request).exclude(status__in=OPEN_EXCLUDE)
        now = timezone.now()
        buckets = {"0-7": 0, "8-15": 0, "16-30": 0, "31-60": 0, "61-90": 0, ">90": 0}
        by_stage = {}
        for c in qs.only("status", "status_changed_at", "created_at"):
            age = (now - c.created_at).days
            b = "0-7" if age <= 7 else "8-15" if age <= 15 else "16-30" if age <= 30 else "31-60" if age <= 60 else "61-90" if age <= 90 else ">90"
            buckets[b] += 1
            by_stage.setdefault(c.status, []).append((now - c.status_changed_at).days)
        return Response({"buckets": [{"bucket": k, "count": v} for k, v in buckets.items()],
                         "avg_days_in_stage": [{"status": k, "avg_days": round(sum(v) / len(v), 1), "count": len(v)} for k, v in by_stage.items()]})


class SLAView(_Base):
    def get(self, request):
        qs = _scoped(request)
        now = timezone.now()
        open_qs = qs.exclude(status__in=OPEN_EXCLUDE)
        rows = open_qs.values("current_owner_role").annotate(total=Count("id"), breached=Count("id", filter=Q(sla_breached=True)), overdue=Count("id", filter=Q(stage_due_at__lt=now)))
        # average turnaround per hop
        def avg_hours(a, b):
            d = qs.exclude(**{f"{a}__isnull": True}).exclude(**{f"{b}__isnull": True}).annotate(dt=ExpressionWrapper(F(b) - F(a), output_field=DurationField())).aggregate(x=Avg("dt"))["x"]
            return round(d.total_seconds() / 3600, 1) if d else None
        return Response({"by_owner_role": list(rows), "avg_hours": {
            "je_submit_to_ae_forward": avg_hours("submitted_at", "ae_forwarded_at"), "ae_forward_to_scn": avg_hours("ae_forwarded_at", "scn_issued_at"),
            "scn_issue_to_service": avg_hours("scn_issued_at", "scn_served_at"), "scn_service_to_decision": avg_hours("scn_served_at", "decided_at"),
            "order_issue_to_service": avg_hours("order_issued_at", "order_served_at"), "order_service_to_execution": avg_hours("order_served_at", "executed_at"),
            "inspection_to_closure": avg_hours("inspected_at", "closed_at")}})


class OfficerPerformanceView(_Base):
    def get(self, request):
        qs = _scoped(request)
        je = qs.values("reported_by__id", "reported_by__first_name", "reported_by__last_name").annotate(cases=Count("id"), submitted=Count("id", filter=~Q(status="DRAFT")), returned=Count("events", filter=Q(events__action="AE_RETURN"), distinct=True), overdue=Count("id", filter=Q(sla_breached=True, current_owner_role="JE")))
        ae = qs.exclude(assigned_ae__isnull=True).values("assigned_ae__id", "assigned_ae__first_name", "assigned_ae__last_name").annotate(cases=Count("id"), pending=Count("id", filter=Q(status__in=["PENDING_AE", "RESPONSE_PENDING_AE"])), overdue=Count("id", filter=Q(sla_breached=True, current_owner_role="AE")))
        jc = qs.exclude(assigned_jc__isnull=True).values("assigned_jc__id", "assigned_jc__first_name", "assigned_jc__last_name").annotate(cases=Count("id"), pending=Count("id", filter=Q(current_owner_role="JC") & ~Q(status__in=OPEN_EXCLUDE)), notices=Count("notices", distinct=True), orders=Count("notices", filter=Q(notices__is_final_order=True), distinct=True), overdue=Count("id", filter=Q(sla_breached=True, current_owner_role="JC")))
        fmt = lambda rows, pre: [{"user_id": r[f"{pre}__id"], "name": f"{r[f'{pre}__first_name']} {r[f'{pre}__last_name']}".strip(), **{k: v for k, v in r.items() if not k.startswith(pre)}} for r in rows]
        return Response({"je": fmt(je, "reported_by"), "ae": fmt(ae, "assigned_ae"), "jc": fmt(jc, "assigned_jc")})


class TrendsView(_Base):
    def get(self, request):
        qs = _scoped(request)
        gran = request.query_params.get("granularity", "month")
        trunc = TruncWeek if gran == "week" else TruncMonth
        created = qs.annotate(p=trunc("created_at")).values("p").annotate(n=Count("id")).order_by("p")
        notices = m.Notice.objects.filter(case__in=qs).annotate(p=trunc("issued_at")).values("p").annotate(n=Count("id"), orders=Count("id", filter=Q(is_final_order=True))).order_by("p")
        execs = m.ExecutionRecord.objects.filter(case__in=qs).annotate(p=trunc("executed_on")).values("p").annotate(n=Count("id"), demol=Count("id", filter=Q(action__in=["DEMOLITION", "PARTIAL_DEMOLITION"])), sealed=Count("id", filter=Q(action="SEALING"))).order_by("p")
        closed = qs.exclude(closed_at__isnull=True).annotate(p=trunc("closed_at")).values("p").annotate(n=Count("id")).order_by("p")
        series = {}
        for name, rows in (("new_cases", created), ("notices", notices), ("executions", execs), ("closed", closed)):
            for r in rows:
                k = r["p"].date().isoformat() if r["p"] else None
                series.setdefault(k, {"period": k})
                series[k][name] = r["n"]
                if name == "notices":
                    series[k]["orders"] = r["orders"]
                if name == "executions":
                    series[k]["demolitions"], series[k]["sealings"] = r["demol"], r["sealed"]
        return Response(sorted((v for k, v in series.items() if k), key=lambda x: x["period"]))


class MapView(_Base):
    """Case pins with status and a short history for pop-ups. ?open=1 open cases only; ?tasks=1 adds planned inspections."""
    def get(self, request):
        from ..services import access
        qs = _scoped(request).exclude(latitude__isnull=True)
        if request.query_params.get("open") == "1":
            qs = qs.exclude(status__in=OPEN_EXCLUDE)
        n_hist = int(access.get_setting("map_history_events", 6) or 6)
        feats = []
        for c in qs.select_related("ward", "reported_by", "assigned_jc").prefetch_related("events", "violations__violation_type")[:5000]:
            hist = [{"at": e.at, "action": e.action, "to": e.to_status, "actor": e.actor_role, "remarks": (e.remarks or "")[:120]} for e in list(c.events.all())[-n_hist:]]
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(c.longitude), float(c.latitude)]},
                          "properties": {"kind": "case", "id": str(c.id), "case_no": c.case_no, "status": c.status, "status_label": c.get_status_display(), "land_type": c.land_type, "priority": c.priority, "address": c.address_line,
                                         "pid": c.pid, "owner": c.owner_name, "ward": c.ward.number if c.ward else None, "sealed": c.sealed, "stop_work": c.stop_work_issued, "litigation": c.litigation_status, "stay_until": c.stay_until,
                                         "violations": [v.violation_type_id for v in c.violations.all()], "scn_issued_at": c.scn_issued_at, "order_issued_at": c.order_issued_at, "compliance_due_at": c.compliance_due_at,
                                         "executed_at": c.executed_at, "updated_at": c.updated_at, "history": hist}})
        if request.query_params.get("tasks") == "1":
            tq = m.InspectionTask.objects.exclude(latitude__isnull=True).select_related("assigned_to")
            if request.query_params.get("open") == "1":
                tq = tq.filter(status__in=["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"])
            for t in tq[:3000]:
                feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(t.longitude), float(t.latitude)]},
                              "properties": {"kind": "task", "id": t.id, "pid": t.pid, "address": t.address, "status": t.status, "status_label": t.get_status_display(), "category": t.category, "due_at": t.due_at,
                                             "assigned_to": t.assigned_to.bvms_profile.display_name if t.assigned_to and hasattr(t.assigned_to, "bvms_profile") else None}})
        return Response({"type": "FeatureCollection", "features": feats})


class UpcomingDeadlinesView(_Base):
    def get(self, request):
        qs = _scoped(request)
        now = timezone.now()
        soon = now + timedelta(days=int(request.query_params.get("days", 7)))
        resp = qs.filter(status="SCN_SERVED", response_due_at__lte=soon).order_by("response_due_at")
        comp = qs.filter(status__in=["ORDER_SERVED"], compliance_due_at__lte=soon).order_by("compliance_due_at")
        hearings = m.Hearing.objects.filter(case__in=qs, held_at__isnull=True, scheduled_at__lte=soon).select_related("case").order_by("scheduled_at")
        appeals = m.Appeal.objects.filter(case__in=qs, status="STAYED", stay_until__isnull=False, stay_until__lte=soon.date()).select_related("case")
        court_dates = m.Appeal.objects.filter(case__in=qs, next_hearing_on__isnull=False, next_hearing_on__lte=soon.date(), next_hearing_on__gte=now.date()).exclude(status__in=["DISMISSED", "ALLOWED", "WITHDRAWN", "DISPOSED"]).select_related("case")
        refs = m.BranchReferral.objects.filter(case__in=qs, status="PENDING", due_at__lte=soon).select_related("case", "branch")
        f = lambda c, dt: {"id": str(c.id), "case_no": c.case_no, "address": c.address_line, "ward": c.ward.number if c.ward else None, "due": dt}
        return Response({"responses_due": [f(c, c.response_due_at) for c in resp[:100]], "compliance_due": [f(c, c.compliance_due_at) for c in comp[:100]],
                         "hearings": [{**f(h.case, h.scheduled_at), "venue": h.venue} for h in hearings[:100]],
                         "stays_expiring": [{**f(a.case, a.stay_until), "authority": a.get_authority_display()} for a in appeals[:100]],
                         "court_dates": [{**f(a.case, a.next_hearing_on), "authority": a.get_authority_display(), "appeal_no": a.appeal_no} for a in court_dates[:100]],
                         "referrals_due": [{**f(r.case, r.due_at), "branch": r.branch.name_en} for r in refs[:100]]})
