"""The case API: list/detail + one endpoint per workflow action."""
from django.db.models import Prefetch, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .. import models as m
from ..services import access
from ..services import workflow as wf
from ..services.audit import verify_chain
from .permissions import HasOfficerProfile, role_of
from . import serializers as s


class ViolationCaseViewSet(viewsets.ModelViewSet):
    permission_classes = [HasOfficerProfile]
    filterset_fields = ("status", "zone", "ward", "division", "land_type", "priority", "source", "current_owner_role", "sla_breached", "stop_work_issued", "sealed", "decision", "reported_by", "assigned_ae", "assigned_jc", "litigation_status", "litigation_authority")
    search_fields = ("case_no", "pid", "address_line", "locality", "sector", "owner_name", "occupier_name", "builder_name")
    ordering_fields = ("created_at", "updated_at", "status_changed_at", "stage_due_at", "response_due_at", "compliance_due_at", "inspected_at")
    ordering = ("-created_at",)
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = (m.ViolationCase.objects.select_related("ward", "zone", "division", "reported_by", "assigned_ae", "assigned_jc", "sanctioned_plan", "govt_parcel")
              .prefetch_related(Prefetch("violations", queryset=m.CaseViolation.objects.select_related("violation_type")), "media"))
        user = self.request.user
        prof = user.bvms_profile
        role = prof.role
        # jurisdiction scoping (admin-configurable: CASE_VIEW_ALL lifts the filter for any role)
        if role in access.MANAGEMENT_ROLES or access.has_perm(user, "CASE_VIEW_ALL"):
            pass
        elif role == "BRANCH_OFFICER":
            qs = qs.filter(Q(referrals__branch=prof.branch) | Q(referrals__assigned_to=user)) if access.has_perm(user, "CASE_VIEW_BRANCH") else qs.none()
        elif role == "JE":
            qs = qs.filter(Q(reported_by=user) | Q(ward__in=prof.wards.all()) | Q(zone__in=prof.zones.all()))
        elif role in ("AE", "XEN"):
            qs = qs.filter(Q(assigned_ae=user) | Q(zone__in=prof.zones.all()) | Q(division__in=prof.divisions.all()))
        elif role == "JC":
            qs = qs.filter(Q(assigned_jc=user) | Q(zone__in=prof.zones.all()))
        elif role == "JC_CLERK":
            parent = prof.parent_profile
            qs = qs.filter(Q(assigned_jc=parent.user) | Q(zone__in=parent.zones.all())) if parent else qs.none()
        elif role == "FIELD_STAFF":
            qs = qs.filter(Q(zone__in=prof.zones.all()) | Q(ward__in=prof.wards.all()))
        mine = self.request.query_params.get("mine")
        if mine == "1":
            qs = qs.filter(Q(reported_by=user) | Q(assigned_ae=user) | Q(assigned_jc=user))
        inbox = self.request.query_params.get("inbox")
        if inbox == "1":
            qs = qs.filter(current_owner_role=role if role != "JC_CLERK" else "JC")
        overdue = self.request.query_params.get("overdue")
        if overdue == "1":
            from django.utils import timezone
            qs = qs.filter(stage_due_at__lt=timezone.now()).exclude(status__in=["CLOSED", "DROPPED", "REGULARISED"])
        return qs.distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return s.ViolationCaseListSerializer
        if self.action == "create":
            return s.CaseCreateSerializer
        return s.ViolationCaseDetailSerializer

    # ---------------- create / update ----------------
    def create(self, request, *args, **kwargs):
        ser = s.CaseCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = dict(ser.validated_data)
        violations = d.pop("violations")
        media_ids = d.pop("media_ids", None)
        submit = d.pop("submit", False)
        case = wf.create_case(request.user, d, violations, request=request, media_ids=media_ids)
        if submit:
            case = wf.submit_to_ae(case, request.user, request=request)
        return Response(s.ViolationCaseDetailSerializer(case, context={"request": request}).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        case = self.get_object()
        data = {k: v for k, v in request.data.items() if k not in ("violations", "media_ids")}
        viol = request.data.get("violations")
        if viol is not None:
            vs = s.CaseViolationInputSerializer(data=viol, many=True)
            vs.is_valid(raise_exception=True)
            viol = vs.validated_data
        case = wf.update_draft(case, request.user, data, viol, request=request)
        return Response(s.ViolationCaseDetailSerializer(case, context={"request": request}).data)

    def _ok(self, case):
        case.refresh_from_db()
        return Response(s.ViolationCaseDetailSerializer(case, context={"request": self.request}).data)

    # ---------------- workflow actions ----------------
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        ser = s.RemarksSerializer(data=request.data); ser.is_valid(raise_exception=True)
        wf.submit_to_ae(self.get_object(), request.user, request=request, remarks=ser.validated_data["remarks"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def ae_forward(self, request, pk=None):
        ser = s.AEForwardSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        wf.ae_forward(self.get_object(), request.user, request=request, remarks=d["remarks"], jc_user=d.get("jc_user"), recommendation=d.get("recommendation", ""))
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def ae_return(self, request, pk=None):
        ser = s.RemarksSerializer(data=request.data); ser.is_valid(raise_exception=True)
        wf.ae_return(self.get_object(), request.user, request=request, remarks=ser.validated_data["remarks"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def issue_notice(self, request, pk=None):
        """JC issues any notice/order/memo (SCN, stop-work, sealing, demolition order, referral ...)."""
        ser = s.IssueNoticeSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        n = wf.jc_issue_notice(self.get_object(), request.user, request=request, order_type_code=d["order_type"], days=d.get("days"), addressee_name=d["addressee_name"],
                               addressee_address=d["addressee_address"], mobiles=d["mobiles"], hearing_at=d.get("hearing_at"), hearing_venue=d["hearing_venue"],
                               operative_text_en=d["operative_text_en"], operative_text_hi=d["operative_text_hi"], remarks=d["remarks"], send_sms=d["send_sms"],
                               is_final_order=d.get("is_final_order"))
        return Response({"notice": s.NoticeSerializer(n, context={"request": request}).data, "case": s.ViolationCaseDetailSerializer(n.case, context={"request": request}).data}, status=201)

    @action(detail=True, methods=["post"])
    def record_service(self, request, pk=None):
        ser = s.RecordServiceSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if d["notice"].case_id != self.get_object().id:
            return Response({"detail": "Notice does not belong to this case"}, status=400)
        wf.record_service(d["notice"], request.user, request=request, mode=d["mode"], served_at=d.get("served_at"), remarks=d["remarks"], media_ids=d["media_ids"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def record_response(self, request, pk=None):
        ser = s.RecordResponseSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        wf.record_response(self.get_object(), request.user, request=request, notice=d.get("notice"), received_on=d["received_on"], received_via=d.get("received_via") or "",
                           summary=d["summary"], submitted_by_name=d["submitted_by_name"], requests_hearing=d["requests_hearing"], media_ids=d["media_ids"], remarks=d["remarks"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def ae_forward_response(self, request, pk=None):
        ser = s.AECommentSerializer(data=request.data); ser.is_valid(raise_exception=True)
        wf.ae_forward_response(ser.validated_data["response"], request.user, request=request, comments=ser.validated_data["comments"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def schedule_hearing(self, request, pk=None):
        ser = s.ScheduleHearingSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        wf.schedule_hearing(self.get_object(), request.user, request=request, scheduled_at=d["scheduled_at"], venue=d["venue"], notice=d.get("notice"), remarks=d["remarks"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def record_hearing(self, request, pk=None):
        ser = s.RecordHearingSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        wf.record_hearing(d["hearing"], request.user, request=request, proceedings=d["proceedings"], attendees=d["attendees"], outcome=d["outcome"], next_date=d.get("next_date"), media_ids=d["media_ids"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def drop(self, request, pk=None):
        ser = s.DropSerializer(data=request.data); ser.is_valid(raise_exception=True)
        wf.jc_drop(self.get_object(), request.user, request=request, remarks=ser.validated_data["remarks"], regularised=ser.validated_data["regularised"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def record_appeal(self, request, pk=None):
        ser = s.RecordAppealSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = dict(ser.validated_data)
        remarks = d.pop("remarks")
        wf.record_appeal(self.get_object(), request.user, request=request, remarks=remarks, **d)
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def decide_appeal(self, request, pk=None):
        """Update the litigation flag: stay extended / vacated, hearing dates, later orders, final decision."""
        ser = s.UpdateAppealSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = dict(ser.validated_data)
        appeal = d.pop("appeal")
        remarks = d.pop("remarks")
        if appeal.case_id != self.get_object().id:
            return Response({"detail": "Appeal does not belong to this case"}, status=400)
        wf.update_appeal(appeal, request.user, request=request, remarks=remarks, **d)
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def update_appeal(self, request, pk=None):
        return self.decide_appeal(request, pk)

    @action(detail=True, methods=["post"])
    def record_execution(self, request, pk=None):
        ser = s.RecordExecutionSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = dict(ser.validated_data)
        remarks = d.pop("remarks")
        wf.record_execution(self.get_object(), request.user, request=request, remarks=remarks, **d)
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        ser = s.RemarksSerializer(data=request.data); ser.is_valid(raise_exception=True)
        wf.verify_and_close(self.get_object(), request.user, request=request, remarks=ser.validated_data["remarks"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        ser = s.RemarksSerializer(data=request.data); ser.is_valid(raise_exception=True)
        wf.reopen(self.get_object(), request.user, request=request, remarks=ser.validated_data["remarks"])
        return self._ok(self.get_object())

    # ---------------- branch referrals & re-assignment ----------------
    @action(detail=True, methods=["post"])
    def refer_branch(self, request, pk=None):
        ser = s.ReferBranchSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        wf.refer_to_branch(self.get_object(), request.user, request=request, branch=d["branch"], query=d["query"], due_days=d.get("due_days"), hold_case=d["hold_case"], assigned_to=d.get("assigned_to"), media_ids=d["media_ids"], remarks=d["remarks"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def respond_branch(self, request, pk=None):
        ser = s.RespondReferralSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if d["referral"].case_id != self.get_object().id:
            return Response({"detail": "Referral does not belong to this case"}, status=400)
        wf.respond_to_referral(d["referral"], request.user, request=request, response=d["response"], recommendation=d["recommendation"], media_ids=d["media_ids"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def close_referral(self, request, pk=None):
        ser = s.CloseReferralSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        wf.close_referral(d["referral"], request.user, request=request, remarks=d["remarks"], withdrawn=d["withdrawn"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def reassign(self, request, pk=None):
        ser = s.ReassignSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        wf.reassign_case(self.get_object(), request.user, request=request, assigned_ae=d.get("assigned_ae"), assigned_jc=d.get("assigned_jc"), reported_by=d.get("reported_by"), remarks=d["remarks"], order_reference=d["order_reference"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        case = self.get_object()
        return Response({"events": s.CaseEventSerializer(case.events.select_related("actor"), many=True).data, "chain": verify_chain(case)})

    @action(detail=True, methods=["get"])
    def notices(self, request, pk=None):
        return Response(s.NoticeSerializer(self.get_object().notices.all(), many=True, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def counts(self, request):
        """Badge counts for the inbox / home screen."""
        qs = self.get_queryset()
        role = role_of(request.user)
        from django.utils import timezone
        return Response({
            "inbox": qs.filter(current_owner_role=role if role != "JC_CLERK" else "JC").exclude(status__in=["CLOSED", "DROPPED", "REGULARISED"]).count(),
            "drafts": qs.filter(status="DRAFT", reported_by=request.user).count(),
            "to_serve": qs.filter(status__in=["SCN_ISSUED", "ORDER_ISSUED"]).count(),
            "execution_due": qs.filter(status="EXECUTION_DUE").count(),
            "overdue": qs.filter(stage_due_at__lt=timezone.now()).exclude(status__in=["CLOSED", "DROPPED", "REGULARISED"]).count(),
            "total_open": qs.exclude(status__in=["CLOSED", "DROPPED", "REGULARISED"]).count(),
        })
