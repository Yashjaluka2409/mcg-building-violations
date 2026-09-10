from django.contrib.auth import get_user_model
from rest_framework import serializers

from .. import models as m

User = get_user_model()


# ---------------------------------------------------------------- masters
class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Zone
        fields = ("id", "code", "name_en", "name_hi", "active")


class DivisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Division
        fields = ("id", "code", "zone", "name_en", "active")


class WardSerializer(serializers.ModelSerializer):
    zone_code = serializers.CharField(source="zone.code", read_only=True)

    class Meta:
        model = m.Ward
        fields = ("id", "number", "name_en", "name_hi", "zone", "zone_code", "division", "active")


class WardGeoSerializer(WardSerializer):
    class Meta(WardSerializer.Meta):
        fields = WardSerializer.Meta.fields + ("boundary",)


class LegalSectionSerializer(serializers.ModelSerializer):
    statute_title = serializers.CharField(source="statute.title", read_only=True)

    class Meta:
        model = m.LegalSection
        fields = ("id", "statute", "statute_title", "section", "heading", "kind", "text", "schedule_fine_inr", "schedule_daily_fine_inr", "verify", "notes")


class ViolationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.ViolationType
        fields = "__all__"


class OrderTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.OrderType
        fields = "__all__"


class SLAConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.SLAConfig
        fields = "__all__"


class UserLiteSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    designation = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "name", "role", "designation")

    def get_name(self, u):
        p = getattr(u, "bvms_profile", None)
        return p.display_name if p else getattr(u, "username", str(u))

    def get_role(self, u):
        p = getattr(u, "bvms_profile", None)
        return p.role if p else None

    def get_designation(self, u):
        p = getattr(u, "bvms_profile", None)
        return p.designation if p else ""


class OfficerProfileSerializer(serializers.ModelSerializer):
    user = UserLiteSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source="user", write_only=True, required=False)
    username = serializers.CharField(write_only=True, required=False)
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = m.OfficerProfile
        fields = ("id", "user", "user_id", "username", "first_name", "last_name", "display_name", "role", "designation", "employee_code", "mobile", "email",
                  "zones", "wards", "divisions", "reports_to", "delegation_order_no", "delegation_order_date", "parent_profile", "active", "created_at")

    def create(self, validated):
        username = validated.pop("username", None)
        first, last = validated.pop("first_name", ""), validated.pop("last_name", "")
        if "user" not in validated:
            if not username:
                username = validated["mobile"]
            user, _ = User.objects.get_or_create(username=username, defaults={"first_name": first, "last_name": last})
            validated["user"] = user
        zones, wards, divs = validated.pop("zones", []), validated.pop("wards", []), validated.pop("divisions", [])
        prof = m.OfficerProfile.objects.create(**validated)
        prof.zones.set(zones); prof.wards.set(wards); prof.divisions.set(divs)
        return prof

    def update(self, inst, validated):
        for k in ("username", "first_name", "last_name"):
            validated.pop(k, None)
        return super().update(inst, validated)


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    name = serializers.CharField()
    role = serializers.CharField(allow_null=True)
    designation = serializers.CharField(allow_blank=True)
    mobile = serializers.CharField(allow_blank=True)
    zones = ZoneSerializer(many=True)
    wards = WardSerializer(many=True)
    delegation_order_no = serializers.CharField(allow_blank=True)
    unread_notifications = serializers.IntegerField()


# ---------------------------------------------------------------- GIS / sanctions
class GovtLandParcelSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.GovtLandParcel
        fields = ("id", "name", "agency", "land_use", "village", "khasra_no", "area_sqm", "ward", "geometry", "bbox", "properties", "active", "created_at")
        read_only_fields = ("bbox",)


class LandLayerUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.LandLayerUpload
        fields = ("id", "name", "agency", "source_file", "feature_count", "uploaded_by", "remarks", "created_at")
        read_only_fields = ("feature_count", "uploaded_by")


class SanctionedPlanSerializer(serializers.ModelSerializer):
    ward_number = serializers.IntegerField(source="ward.number", read_only=True)
    documents = serializers.SerializerMethodField()

    class Meta:
        model = m.SanctionedPlan
        fields = "__all__"
        read_only_fields = ("created_by", "source")

    def get_documents(self, obj):
        return MediaAttachmentSerializer(obj.documents.all(), many=True, context=self.context).data


# ---------------------------------------------------------------- media
class MediaAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    uploaded_by = UserLiteSerializer(read_only=True)

    class Meta:
        model = m.MediaAttachment
        fields = ("id", "case", "notice", "kind", "media_type", "url", "original_name", "size_bytes", "sha256", "latitude", "longitude",
                  "accuracy_m", "captured_at", "device_id", "distance_from_case_m", "geotag_verified", "caption", "uploaded_by", "created_at")
        read_only_fields = ("sha256", "size_bytes", "distance_from_case_m", "geotag_verified")

    def get_url(self, obj):
        req = self.context.get("request")
        try:
            return req.build_absolute_uri(obj.file.url) if req else obj.file.url
        except Exception:
            return None


class MediaUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    kind = serializers.ChoiceField(choices=m.MediaKind.choices, default=m.MediaKind.INSPECTION)
    case = serializers.PrimaryKeyRelatedField(queryset=m.ViolationCase.objects.all(), required=False, allow_null=True)
    notice = serializers.PrimaryKeyRelatedField(queryset=m.Notice.objects.all(), required=False, allow_null=True)
    sanctioned_plan = serializers.PrimaryKeyRelatedField(queryset=m.SanctionedPlan.objects.all(), required=False, allow_null=True)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    accuracy_m = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)
    altitude_m = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)
    captured_at = serializers.DateTimeField(required=False, allow_null=True)
    device_id = serializers.CharField(required=False, allow_blank=True)
    caption = serializers.CharField(required=False, allow_blank=True)


# ---------------------------------------------------------------- case parts
class CaseViolationSerializer(serializers.ModelSerializer):
    violation_type = ViolationTypeSerializer(read_only=True)
    code = serializers.CharField(source="violation_type.code", read_only=True)

    class Meta:
        model = m.CaseViolation
        fields = ("id", "code", "violation_type", "details", "remarks", "is_primary")


class CaseViolationInputSerializer(serializers.Serializer):
    code = serializers.CharField()
    details = serializers.JSONField(required=False)
    remarks = serializers.CharField(required=False, allow_blank=True)
    is_primary = serializers.BooleanField(required=False, default=False)

    def validate_code(self, v):
        if not m.ViolationType.objects.filter(code=v, active=True).exists():
            raise serializers.ValidationError(f"Unknown violation code {v}")
        return v


class NoticeDispatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.NoticeDispatch
        fields = ("id", "channel", "to", "status", "provider_ref", "attempts", "last_error", "sent_at", "created_at")


class NoticeSerializer(serializers.ModelSerializer):
    order_type = OrderTypeSerializer(read_only=True)
    issued_by = UserLiteSerializer(read_only=True)
    served_by = UserLiteSerializer(read_only=True)
    dispatches = NoticeDispatchSerializer(many=True, read_only=True)
    pdf_url = serializers.SerializerMethodField()
    signed_pdf_url = serializers.SerializerMethodField()
    case_no = serializers.CharField(source="case.case_no", read_only=True)
    delivery_media = serializers.SerializerMethodField()

    class Meta:
        model = m.Notice
        fields = ("id", "case", "case_no", "order_type", "notice_no", "kind", "issued_by", "issued_at", "addressee_name", "addressee_address", "addressee_mobiles",
                  "response_days", "response_due_at", "compliance_days", "compliance_due_at", "hearing_at", "hearing_venue", "operative_text_en", "operative_text_hi",
                  "pdf_url", "signed_pdf_url", "document_hash", "verification_code", "qr_payload", "signature_status", "signer_name", "signer_cert_subject", "signed_at",
                  "signature_error", "served_at", "served_mode", "served_by", "service_remarks", "is_final_order", "dispatches", "delivery_media", "created_at")

    def _abs(self, f):
        req = self.context.get("request")
        if not f:
            return None
        return req.build_absolute_uri(f.url) if req else f.url

    def get_pdf_url(self, o):
        return self._abs(o.pdf)

    def get_signed_pdf_url(self, o):
        return self._abs(o.signed_pdf)

    def get_delivery_media(self, o):
        return MediaAttachmentSerializer(o.media.all(), many=True, context=self.context).data


class CaseResponseSerializer(serializers.ModelSerializer):
    uploaded_by = UserLiteSerializer(read_only=True)
    notice_no = serializers.CharField(source="notice.notice_no", read_only=True)

    class Meta:
        model = m.CaseResponse
        fields = "__all__"


class HearingSerializer(serializers.ModelSerializer):
    presiding = UserLiteSerializer(read_only=True)

    class Meta:
        model = m.Hearing
        fields = "__all__"


class AppealSerializer(serializers.ModelSerializer):
    recorded_by = UserLiteSerializer(read_only=True)

    class Meta:
        model = m.Appeal
        fields = "__all__"


class ExecutionRecordSerializer(serializers.ModelSerializer):
    recorded_by = UserLiteSerializer(read_only=True)
    verified_by = UserLiteSerializer(read_only=True)

    class Meta:
        model = m.ExecutionRecord
        fields = "__all__"


class CaseEventSerializer(serializers.ModelSerializer):
    actor = UserLiteSerializer(read_only=True)

    class Meta:
        model = m.CaseEvent
        fields = ("id", "at", "actor", "actor_role", "action", "from_status", "to_status", "remarks", "payload", "latitude", "longitude", "hash", "prev_hash")


class NotificationSerializer(serializers.ModelSerializer):
    case_no = serializers.CharField(source="case.case_no", read_only=True, default=None)

    class Meta:
        model = m.Notification
        fields = ("id", "case", "case_no", "title", "body", "level", "read_at", "created_at")


# ---------------------------------------------------------------- the case
class ViolationCaseListSerializer(serializers.ModelSerializer):
    ward_number = serializers.IntegerField(source="ward.number", read_only=True, default=None)
    zone_code = serializers.CharField(source="zone.code", read_only=True, default=None)
    reported_by = UserLiteSerializer(read_only=True)
    assigned_ae = UserLiteSerializer(read_only=True)
    assigned_jc = UserLiteSerializer(read_only=True)
    violation_codes = serializers.SerializerMethodField()
    primary_violation = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    days_in_stage = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = m.ViolationCase
        fields = ("id", "case_no", "status", "status_display", "priority", "source", "pid", "address_line", "locality", "sector", "ward", "ward_number", "zone", "zone_code",
                  "latitude", "longitude", "land_type", "owner_name", "construction_stage", "reported_by", "assigned_ae", "assigned_jc", "current_owner_role",
                  "stage_due_at", "sla_breached", "inspected_at", "scn_issued_at", "response_due_at", "compliance_due_at", "decision", "stop_work_issued", "sealed",
                  "violation_codes", "primary_violation", "days_in_stage", "thumbnail", "created_at", "updated_at")

    def get_violation_codes(self, o):
        return [cv.violation_type_id for cv in o.violations.all()]

    def get_primary_violation(self, o):
        cv = next((c for c in o.violations.all() if c.is_primary), None) or next(iter(o.violations.all()), None)
        return {"code": cv.violation_type_id, "title_en": cv.violation_type.title_en, "category": cv.violation_type.category} if cv else None

    def get_days_in_stage(self, o):
        from django.utils import timezone
        return (timezone.now() - o.status_changed_at).days

    def get_thumbnail(self, o):
        req = self.context.get("request")
        mm = next((x for x in o.media.all() if x.media_type == "IMAGE"), None)
        if not mm:
            return None
        try:
            return req.build_absolute_uri(mm.file.url) if req else mm.file.url
        except Exception:
            return None


class ViolationCaseDetailSerializer(ViolationCaseListSerializer):
    violations = CaseViolationSerializer(many=True, read_only=True)
    media = MediaAttachmentSerializer(many=True, read_only=True)
    notices = NoticeSerializer(many=True, read_only=True)
    responses = CaseResponseSerializer(many=True, read_only=True)
    hearings = HearingSerializer(many=True, read_only=True)
    appeals = AppealSerializer(many=True, read_only=True)
    executions = ExecutionRecordSerializer(many=True, read_only=True)
    events = CaseEventSerializer(many=True, read_only=True)
    sanctioned_plan = SanctionedPlanSerializer(read_only=True)
    govt_parcel = GovtLandParcelSerializer(read_only=True)
    available_actions = serializers.SerializerMethodField()
    available_order_types = serializers.SerializerMethodField()

    class Meta(ViolationCaseListSerializer.Meta):
        fields = ViolationCaseListSerializer.Meta.fields + (
            "complaint_ref", "pid_snapshot", "pid_linked_mobile", "alternate_mobile", "village_colony", "pincode", "division", "location_accuracy_m",
            "govt_parcel", "sanctioned_plan", "owner_father_name", "occupier_name", "builder_name", "person_on_site", "plot_area_sqm", "covered_area_sqm",
            "storeys", "height_m", "use_observed", "description", "measurements", "submitted_at", "ae_forwarded_at", "jc_received_at", "scn_served_at",
            "response_received_at", "hearing_at", "decided_at", "order_issued_at", "order_served_at", "executed_at", "closed_at", "decision_reasons", "final_order",
            "closure_reason", "demolition_cost_inr", "cost_recovery_status", "violations", "media", "notices", "responses", "hearings", "appeals", "executions",
            "events", "available_actions", "available_order_types")

    def get_available_actions(self, o):
        from ..services.workflow import available_actions
        req = self.context.get("request")
        return available_actions(o, req.user) if req else []

    def get_available_order_types(self, o):
        codes = set()
        for cv in o.violations.all():
            codes.update(cv.violation_type.orders_available or [])
        return OrderTypeSerializer(m.OrderType.objects.filter(code__in=codes, active=True), many=True).data


class CaseCreateSerializer(serializers.Serializer):
    source = serializers.CharField(required=False, default="FIELD_INSPECTION")
    complaint_ref = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(choices=["LOW", "NORMAL", "HIGH", "URGENT"], required=False, default="NORMAL")
    pid = serializers.CharField(required=False, allow_blank=True)
    pid_snapshot = serializers.JSONField(required=False)
    pid_linked_mobile = serializers.CharField(required=False, allow_blank=True)
    alternate_mobile = serializers.CharField(required=False, allow_blank=True)
    address_line = serializers.CharField()
    locality = serializers.CharField(required=False, allow_blank=True)
    sector = serializers.CharField(required=False, allow_blank=True)
    village_colony = serializers.CharField(required=False, allow_blank=True)
    pincode = serializers.CharField(required=False, allow_blank=True)
    ward = serializers.PrimaryKeyRelatedField(queryset=m.Ward.objects.all(), required=False, allow_null=True)
    zone = serializers.PrimaryKeyRelatedField(queryset=m.Zone.objects.all(), required=False, allow_null=True)
    division = serializers.PrimaryKeyRelatedField(queryset=m.Division.objects.all(), required=False, allow_null=True)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    location_accuracy_m = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)
    land_type = serializers.ChoiceField(choices=m.LandType.choices, required=False, default=m.LandType.UNKNOWN)
    sanctioned_plan = serializers.PrimaryKeyRelatedField(queryset=m.SanctionedPlan.objects.all(), required=False, allow_null=True)
    owner_name = serializers.CharField(required=False, allow_blank=True)
    owner_father_name = serializers.CharField(required=False, allow_blank=True)
    occupier_name = serializers.CharField(required=False, allow_blank=True)
    builder_name = serializers.CharField(required=False, allow_blank=True)
    person_on_site = serializers.CharField(required=False, allow_blank=True)
    construction_stage = serializers.ChoiceField(choices=m.ConstructionStage.choices, required=False, default=m.ConstructionStage.UNDER_CONSTRUCTION)
    plot_area_sqm = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    covered_area_sqm = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    storeys = serializers.CharField(required=False, allow_blank=True)
    height_m = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)
    use_observed = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField()
    measurements = serializers.JSONField(required=False)
    inspected_at = serializers.DateTimeField(required=False)
    violations = CaseViolationInputSerializer(many=True)
    media_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    submit = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not attrs.get("pid") and not attrs.get("address_line"):
            raise serializers.ValidationError("Either PID or address is required")
        if not attrs.get("violations"):
            raise serializers.ValidationError({"violations": "Select at least one violation"})
        return attrs


class RemarksSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class AEForwardSerializer(RemarksSerializer):
    jc_user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    recommendation = serializers.ChoiceField(choices=["SCN", "STOP_WORK", "SEALING", "DEMOLITION", "DROP", "REGULARISE", "REFER"], required=False, allow_blank=True)


class IssueNoticeSerializer(RemarksSerializer):
    order_type = serializers.CharField()
    days = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=365)
    addressee_name = serializers.CharField(required=False, allow_blank=True, default="")
    addressee_address = serializers.CharField(required=False, allow_blank=True, default="")
    mobiles = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    hearing_at = serializers.DateTimeField(required=False, allow_null=True)
    hearing_venue = serializers.CharField(required=False, allow_blank=True, default="")
    operative_text_en = serializers.CharField(required=False, allow_blank=True, default="")
    operative_text_hi = serializers.CharField(required=False, allow_blank=True, default="")
    send_sms = serializers.BooleanField(required=False, default=True)
    is_final_order = serializers.BooleanField(required=False, allow_null=True, default=None)


class RecordServiceSerializer(RemarksSerializer):
    notice = serializers.PrimaryKeyRelatedField(queryset=m.Notice.objects.all())
    mode = serializers.ChoiceField(choices=m.Notice.ServiceMode.choices)
    served_at = serializers.DateTimeField(required=False, allow_null=True)
    media_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class RecordResponseSerializer(RemarksSerializer):
    notice = serializers.PrimaryKeyRelatedField(queryset=m.Notice.objects.all(), required=False, allow_null=True)
    received_on = serializers.DateField()
    received_via = serializers.ChoiceField(choices=m.CaseResponse.ReceivedVia.choices, required=False, allow_blank=True)
    submitted_by_name = serializers.CharField(required=False, allow_blank=True, default="")
    summary = serializers.CharField()
    requests_hearing = serializers.BooleanField(required=False, default=False)
    media_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class AECommentSerializer(serializers.Serializer):
    response = serializers.PrimaryKeyRelatedField(queryset=m.CaseResponse.objects.all())
    comments = serializers.CharField()


class ScheduleHearingSerializer(RemarksSerializer):
    scheduled_at = serializers.DateTimeField()
    venue = serializers.CharField(required=False, allow_blank=True, default="Office of the Joint Commissioner, MCG")
    notice = serializers.PrimaryKeyRelatedField(queryset=m.Notice.objects.all(), required=False, allow_null=True)


class RecordHearingSerializer(serializers.Serializer):
    hearing = serializers.PrimaryKeyRelatedField(queryset=m.Hearing.objects.all())
    proceedings = serializers.CharField(required=False, allow_blank=True, default="")
    attendees = serializers.CharField(required=False, allow_blank=True, default="")
    outcome = serializers.ChoiceField(choices=["HEARD", "ADJOURNED", "EX_PARTE"], default="HEARD")
    next_date = serializers.DateTimeField(required=False, allow_null=True)
    media_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class RecordAppealSerializer(RemarksSerializer):
    filed_on = serializers.DateField()
    authority = serializers.CharField()
    appeal_no = serializers.CharField(required=False, allow_blank=True, default="")
    stay_granted = serializers.BooleanField(required=False, default=False)
    stay_until = serializers.DateField(required=False, allow_null=True)
    conditions = serializers.CharField(required=False, allow_blank=True, default="")
    order = serializers.PrimaryKeyRelatedField(queryset=m.Notice.objects.all(), required=False, allow_null=True)
    media_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class DecideAppealSerializer(serializers.Serializer):
    appeal = serializers.PrimaryKeyRelatedField(queryset=m.Appeal.objects.all())
    status = serializers.ChoiceField(choices=["PENDING", "STAYED", "DISMISSED", "ALLOWED", "MODIFIED", "WITHDRAWN"])
    decided_on = serializers.DateField()
    decision_summary = serializers.CharField(required=False, allow_blank=True, default="")
    new_compliance_days = serializers.IntegerField(required=False, allow_null=True)
    media_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class RecordExecutionSerializer(RemarksSerializer):
    action = serializers.ChoiceField(choices=m.ExecutionRecord.Action.choices)
    mode = serializers.ChoiceField(choices=m.ExecutionRecord.Mode.choices)
    executed_on = serializers.DateTimeField()
    media_ids = serializers.ListField(child=serializers.UUIDField())
    squad_incharge = serializers.CharField(required=False, allow_blank=True, default="")
    police_assistance = serializers.BooleanField(required=False, default=False)
    police_station = serializers.CharField(required=False, allow_blank=True, default="")
    duty_magistrate = serializers.CharField(required=False, allow_blank=True, default="")
    machinery_used = serializers.CharField(required=False, allow_blank=True, default="")
    area_demolished_sqm = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    seal_memo_no = serializers.CharField(required=False, allow_blank=True, default="")
    cost_incurred_inr = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)


class DropSerializer(serializers.Serializer):
    remarks = serializers.CharField()
    regularised = serializers.BooleanField(required=False, default=False)


class OTPRequestSerializer(serializers.Serializer):
    mobile = serializers.CharField()


class OTPVerifySerializer(serializers.Serializer):
    mobile = serializers.CharField()
    otp = serializers.CharField()
    device_id = serializers.CharField(required=False, allow_blank=True)
