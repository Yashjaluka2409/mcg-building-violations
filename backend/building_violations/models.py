"""
Data model of the MCG Building Violation Management System (BVMS).

Design notes for the IT team
----------------------------
* All tables are prefixed ``bvms_`` so they sit safely beside the platform's tables.
* Users: the module uses ``settings.AUTH_USER_MODEL`` (the platform's user table when mounted
  inside sms-be) and keeps its own ``OfficerProfile`` for role / jurisdiction, so no change to the
  platform's user model is needed.
* Geometry is stored as GeoJSON in JSONFields (no PostGIS/GDAL requirement). Point-in-polygon
  tests use ``shapely``. If the platform already has PostGIS, ``GovtLandParcel.geometry`` can be
  swapped for a ``PolygonField`` without touching the API.
* Every state change writes a hash-chained ``CaseEvent`` row (tamper-evident audit trail).
"""
from __future__ import annotations

import hashlib
import json
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


# ============================================================================
# 0. Helpers
# ============================================================================
class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def media_upload_path(instance, filename):
    today = timezone.now()
    return f"bvms/{today:%Y/%m}/{uuid.uuid4().hex}_{filename[-80:]}"


def notice_pdf_path(instance, filename):
    return f"bvms/notices/{timezone.now():%Y/%m}/{filename}"


# ============================================================================
# 1. Masters: jurisdiction, officers, legal catalogue
# ============================================================================
class Zone(models.Model):
    code = models.CharField(max_length=10, unique=True)      # e.g. "1", "2", "3", "4"
    name_en = models.CharField(max_length=80)
    name_hi = models.CharField(max_length=80, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "bvms_zone"
        ordering = ["code"]

    def __str__(self):
        return f"Zone {self.code}"


class Division(models.Model):
    code = models.CharField(max_length=10, unique=True)      # "1A", "1B", ... "4B"
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="divisions")
    name_en = models.CharField(max_length=80, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "bvms_division"
        ordering = ["code"]

    def __str__(self):
        return f"Division {self.code}"


class Ward(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)    # 1..36
    name_en = models.CharField(max_length=120, blank=True)
    name_hi = models.CharField(max_length=120, blank=True)
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="wards")
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True, blank=True, related_name="wards")
    boundary = models.JSONField(null=True, blank=True, help_text="GeoJSON Polygon/MultiPolygon (WGS84)")
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "bvms_ward"
        ordering = ["number"]

    def __str__(self):
        return f"Ward {self.number}"


class Role(models.TextChoices):
    JE = "JE", "Junior Engineer (field)"
    AE = "AE", "Assistant Engineer"
    XEN = "XEN", "Executive Engineer"
    JC = "JC", "Joint Commissioner"
    JC_CLERK = "JC_CLERK", "JC office clerk (response upload only)"
    ADDL_COMMISSIONER = "ADDL_COMMISSIONER", "Additional Commissioner"
    COMMISSIONER = "COMMISSIONER", "Commissioner"
    FIELD_STAFF = "FIELD_STAFF", "Enforcement / demolition squad"
    ADMIN = "ADMIN", "Module administrator"
    VIEWER = "VIEWER", "Read-only (MIS)"


class OfficerProfile(TimeStamped):
    """Role and jurisdiction of a platform user inside this module."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bvms_profile")
    role = models.CharField(max_length=24, choices=Role.choices)
    designation = models.CharField(max_length=120, blank=True)
    employee_code = models.CharField(max_length=40, blank=True)
    mobile = models.CharField(max_length=15, db_index=True)
    email = models.EmailField(blank=True)
    zones = models.ManyToManyField(Zone, blank=True, related_name="officers")
    wards = models.ManyToManyField(Ward, blank=True, related_name="officers")
    divisions = models.ManyToManyField(Division, blank=True, related_name="officers")
    reports_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="subordinates")
    # For JC: the Commissioner's delegation order under s.401(2) HMC Act quoted on every notice.
    delegation_order_no = models.CharField(max_length=120, blank=True)
    delegation_order_date = models.DateField(null=True, blank=True)
    signature_image = models.ImageField(upload_to="bvms/signatures/", null=True, blank=True)
    parent_profile = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="sub_logins",
                                       help_text="For JC_CLERK: the JC whose office this clerk belongs to")
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "bvms_officer_profile"

    def __str__(self):
        return f"{self.role} {self.user}"

    @property
    def display_name(self):
        u = self.user
        full = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        return full or getattr(u, "username", "") or str(u)


class LegalStatute(models.Model):
    code = models.CharField(max_length=20, primary_key=True)  # HMCA1994 ...
    title = models.CharField(max_length=200)
    citation = models.CharField(max_length=300, blank=True)
    jurisdiction = models.CharField(max_length=200, blank=True)
    primary = models.BooleanField(default=True)

    class Meta:
        db_table = "bvms_legal_statute"

    def __str__(self):
        return self.title


class LegalSection(models.Model):
    statute = models.ForeignKey(LegalStatute, on_delete=models.CASCADE, related_name="sections")
    section = models.CharField(max_length=30)
    heading = models.CharField(max_length=300)
    kind = models.CharField(max_length=20, default="substantive")
    text = models.TextField()
    schedule_fine_inr = models.PositiveIntegerField(null=True, blank=True)
    schedule_daily_fine_inr = models.PositiveIntegerField(null=True, blank=True)
    verify = models.BooleanField(default=False, help_text="Text extracted from scan - to be verified against Gazette")
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "bvms_legal_section"
        unique_together = ("statute", "section")
        ordering = ["statute", "id"]

    def __str__(self):
        return f"{self.statute_id} s.{self.section}"


class ViolationCategory(models.TextChoices):
    GOVT_LAND = "GOVT_LAND", "Government / Corporation land"
    PRIVATE_LAND_NO_SANCTION = "PRIVATE_LAND_NO_SANCTION", "Private land - no sanction"
    DEVIATION_FROM_SANCTION = "DEVIATION_FROM_SANCTION", "Deviation from sanction"
    STREET_ENCROACHMENT = "STREET_ENCROACHMENT", "Street encroachment"
    MISUSE_CHANGE_OF_USE = "MISUSE_CHANGE_OF_USE", "Misuse / change of use"
    DANGEROUS_UNFIT = "DANGEROUS_UNFIT", "Dangerous / unfit"
    PROCEDURAL_NON_COMPLIANCE = "PROCEDURAL_NON_COMPLIANCE", "Non-compliance with orders"


class ViolationType(models.Model):
    code = models.CharField(max_length=10, primary_key=True)  # GL-01 ...
    category = models.CharField(max_length=40, choices=ViolationCategory.choices)
    title_en = models.CharField(max_length=250)
    title_hi = models.CharField(max_length=250, blank=True)
    description = models.TextField(blank=True)
    contravention_of = models.TextField(blank=True, help_text="Phrase printed in the notice")
    legal_basis = models.JSONField(default=list)          # [{statute, section}]
    action_path = models.CharField(max_length=30)        # HMCA_261, HMCA_408A, ...
    orders_available = models.JSONField(default=list)    # order type codes
    scn_response_days_default = models.PositiveSmallIntegerField(default=7)
    order_compliance_days_default = models.PositiveSmallIntegerField(default=15)
    statutory_minimum_days = models.PositiveSmallIntegerField(default=0)
    severity = models.CharField(max_length=10, default="HIGH")
    compoundable = models.CharField(max_length=12, default="NO")
    evidence_checklist = models.JSONField(default=list)
    schedule_fine_inr = models.PositiveIntegerField(null=True, blank=True)
    schedule_daily_fine_inr = models.PositiveIntegerField(null=True, blank=True)
    appeal = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "bvms_violation_type"
        ordering = ["sort_order", "code"]

    def __str__(self):
        return f"{self.code} {self.title_en}"


class OrderType(models.Model):
    code = models.CharField(max_length=40, primary_key=True)  # SCN_261, DEMOLITION_ORDER_261 ...
    title_en = models.CharField(max_length=250)
    title_hi = models.CharField(max_length=250, blank=True)
    statute = models.CharField(max_length=20)
    section = models.CharField(max_length=30)
    kind = models.CharField(max_length=12)  # NOTICE | ORDER | MEMO | REFERRAL
    min_days = models.PositiveSmallIntegerField(default=0)
    default_days = models.PositiveSmallIntegerField(default=0)
    template = models.CharField(max_length=80)
    appeal_days = models.PositiveSmallIntegerField(null=True, blank=True)
    appeal_to = models.CharField(max_length=200, blank=True)
    body_override_en = models.TextField(blank=True, help_text="Admin-editable operative text (optional)")
    body_override_hi = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "bvms_order_type"

    def __str__(self):
        return self.title_en


class SLAConfig(models.Model):
    """Turn-around time per workflow stage; escalation goes to `escalate_to_role`."""
    stage = models.CharField(max_length=40, unique=True)   # e.g. PENDING_AE
    label = models.CharField(max_length=120)
    hours = models.PositiveIntegerField(default=72)
    escalate_to_role = models.CharField(max_length=24, choices=Role.choices, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "bvms_sla_config"

    def __str__(self):
        return f"{self.stage}: {self.hours}h"


# ============================================================================
# 2. GIS: government land parcels
# ============================================================================
class LandOwningAgency(models.TextChoices):
    MCG = "MCG", "Municipal Corporation Gurugram"
    HSVP = "HSVP", "Haryana Shahari Vikas Pradhikaran"
    GMDA = "GMDA", "Gurugram Metropolitan Development Authority"
    STATE_GOVT = "STATE_GOVT", "State Government (other departments)"
    PWD = "PWD", "PWD (B&R)"
    IRRIGATION = "IRRIGATION", "Irrigation & Water Resources"
    FOREST = "FOREST", "Forest Department"
    PANCHAYAT = "PANCHAYAT", "Gram Panchayat / Shamlat Deh"
    RAILWAYS = "RAILWAYS", "Railways"
    NHAI = "NHAI", "NHAI"
    DEFENCE = "DEFENCE", "Defence"
    OTHER = "OTHER", "Other"


class LandLayerUpload(TimeStamped):
    name = models.CharField(max_length=200)
    agency = models.CharField(max_length=20, choices=LandOwningAgency.choices)
    source_file = models.FileField(upload_to="bvms/land-layers/")
    feature_count = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    remarks = models.TextField(blank=True)

    class Meta:
        db_table = "bvms_land_layer_upload"


class GovtLandParcel(TimeStamped):
    name = models.CharField(max_length=200, blank=True)
    agency = models.CharField(max_length=20, choices=LandOwningAgency.choices, default=LandOwningAgency.MCG)
    land_use = models.CharField(max_length=120, blank=True)   # park, green belt, road, community site...
    village = models.CharField(max_length=120, blank=True)
    khasra_no = models.CharField(max_length=120, blank=True)
    area_sqm = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    ward = models.ForeignKey(Ward, null=True, blank=True, on_delete=models.SET_NULL)
    geometry = models.JSONField(help_text="GeoJSON Polygon / MultiPolygon (WGS84)")
    bbox = models.JSONField(default=list, help_text="[minx, miny, maxx, maxy] for quick filtering")
    properties = models.JSONField(default=dict, blank=True)
    layer_upload = models.ForeignKey(LandLayerUpload, null=True, blank=True, on_delete=models.SET_NULL, related_name="parcels")
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "bvms_govt_land_parcel"

    def __str__(self):
        return f"{self.agency} {self.name or self.khasra_no}"


# ============================================================================
# 3. Sanctioned building plans / licences register
# ============================================================================
class SanctionedPlan(TimeStamped):
    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Entered manually"
        BULK_UPLOAD = "BULK_UPLOAD", "Excel/CSV upload"
        PLATFORM_SYNC = "PLATFORM_SYNC", "Synced from MCG building-plan module"

    plan_no = models.CharField(max_length=80, unique=True)   # BR-I / sanction number
    pid = models.CharField(max_length=40, blank=True, db_index=True)
    address = models.TextField()
    ward = models.ForeignKey(Ward, null=True, blank=True, on_delete=models.SET_NULL)
    zone = models.ForeignKey(Zone, null=True, blank=True, on_delete=models.SET_NULL)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    owner_name = models.CharField(max_length=200)
    owner_mobile = models.CharField(max_length=15, blank=True)
    plot_area_sqm = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    land_use = models.CharField(max_length=60, blank=True)          # residential / commercial / industrial / institutional
    building_type = models.CharField(max_length=80, blank=True)
    sanctioned_on = models.DateField()
    valid_till = models.DateField(null=True, blank=True)
    sanction_mode = models.CharField(max_length=40, blank=True)     # regular / self-certification / deemed
    permitted_floors = models.CharField(max_length=40, blank=True)   # "S+4", "B+G+3"
    permitted_ground_coverage_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    permitted_far = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    permitted_height_m = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    setbacks = models.JSONField(default=dict, blank=True)            # {"front": 3, "rear": 3, "side1": 0, "side2": 0}
    # Colony licence / other licence details
    licence_no = models.CharField(max_length=80, blank=True)
    licence_holder = models.CharField(max_length=200, blank=True)
    licence_date = models.DateField(null=True, blank=True)
    licence_valid_till = models.DateField(null=True, blank=True)
    licence_authority = models.CharField(max_length=120, blank=True)   # DTCP / MCG / HSVP
    colony_name = models.CharField(max_length=160, blank=True)
    architect_name = models.CharField(max_length=160, blank=True)
    architect_registration_no = models.CharField(max_length=80, blank=True)
    dpc_certificate_on = models.DateField(null=True, blank=True)
    occupation_certificate_no = models.CharField(max_length=80, blank=True)
    occupation_certificate_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default="VALID")        # VALID / EXPIRED / REVOKED / COMPLETED
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    external_ref = models.CharField(max_length=120, blank=True)
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        db_table = "bvms_sanctioned_plan"
        ordering = ["-sanctioned_on"]

    def __str__(self):
        return self.plan_no


# ============================================================================
# 4. Media (geotagged photos / videos / documents)
# ============================================================================
class MediaKind(models.TextChoices):
    INSPECTION = "INSPECTION", "Inspection evidence"
    NOTICE_DELIVERY = "NOTICE_DELIVERY", "Proof of delivery of notice"
    ORDER_DELIVERY = "ORDER_DELIVERY", "Proof of delivery of order"
    RESPONSE = "RESPONSE", "Response / reply document"
    HEARING = "HEARING", "Hearing record"
    EXECUTION = "EXECUTION", "Demolition / sealing evidence"
    COMPLIANCE = "COMPLIANCE", "Self-compliance evidence"
    APPEAL = "APPEAL", "Appeal / court order"
    SANCTION_DOC = "SANCTION_DOC", "Sanction / licence document"
    OTHER = "OTHER", "Other"


class MediaAttachment(TimeStamped):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey("ViolationCase", null=True, blank=True, on_delete=models.CASCADE, related_name="media")
    notice = models.ForeignKey("Notice", null=True, blank=True, on_delete=models.SET_NULL, related_name="media")
    sanctioned_plan = models.ForeignKey(SanctionedPlan, null=True, blank=True, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=20, choices=MediaKind.choices, default=MediaKind.INSPECTION)
    media_type = models.CharField(max_length=10, default="IMAGE")   # IMAGE | VIDEO | PDF | DOC
    file = models.FileField(upload_to=media_upload_path)
    original_name = models.CharField(max_length=255, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    # Geo-tag captured by the app at the moment of capture (not from EXIF only)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    accuracy_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    altitude_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    device_id = models.CharField(max_length=120, blank=True)
    distance_from_case_m = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    geotag_verified = models.BooleanField(default=False)
    caption = models.CharField(max_length=300, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        db_table = "bvms_media"
        ordering = ["-created_at"]


# ============================================================================
# 5. The case
# ============================================================================
class CaseStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft (JE)"
    PENDING_AE = "PENDING_AE", "Pending with AE"
    RETURNED_TO_JE = "RETURNED_TO_JE", "Returned to JE for re-inspection"
    PENDING_JC = "PENDING_JC", "Pending with JC"
    SCN_ISSUED = "SCN_ISSUED", "Show cause notice issued"
    SCN_SERVED = "SCN_SERVED", "SCN served - response awaited"
    RESPONSE_RECEIVED = "RESPONSE_RECEIVED", "Response received"
    RESPONSE_PENDING_AE = "RESPONSE_PENDING_AE", "Response with AE for comments"
    RESPONSE_PENDING_JC = "RESPONSE_PENDING_JC", "Response with JC for decision"
    NO_RESPONSE = "NO_RESPONSE", "No response within time"
    HEARING_SCHEDULED = "HEARING_SCHEDULED", "Hearing scheduled"
    ORDER_ISSUED = "ORDER_ISSUED", "Final order issued"
    ORDER_SERVED = "ORDER_SERVED", "Order served - compliance period running"
    APPEAL_STAY = "APPEAL_STAY", "Stayed in appeal"
    EXECUTION_DUE = "EXECUTION_DUE", "Compliance period over - execution due"
    COMPLIED = "COMPLIED", "Complied by owner"
    EXECUTED = "EXECUTED", "Demolished / sealed by MCG"
    CLOSED = "CLOSED", "Closed"
    DROPPED = "DROPPED", "Dropped - no violation"
    REGULARISED = "REGULARISED", "Regularised / compounded"


class LandType(models.TextChoices):
    GOVT_MCG = "GOVT_MCG", "Land vested in MCG"
    GOVT_STATE = "GOVT_STATE", "State Govt / other public land"
    PRIVATE = "PRIVATE", "Private land"
    UNKNOWN = "UNKNOWN", "Not yet determined"


class ConstructionStage(models.TextChoices):
    PLINTH = "PLINTH", "Plinth / foundation"
    UNDER_CONSTRUCTION = "UNDER_CONSTRUCTION", "Under construction"
    COMPLETED = "COMPLETED", "Completed"
    OCCUPIED = "OCCUPIED", "Completed and occupied"


class Sequence(models.Model):
    """Atomic counters for case / notice numbering."""
    key = models.CharField(max_length=60, primary_key=True)
    value = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "bvms_sequence"


class ViolationCase(TimeStamped):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case_no = models.CharField(max_length=40, unique=True, db_index=True)
    status = models.CharField(max_length=30, choices=CaseStatus.choices, default=CaseStatus.DRAFT, db_index=True)
    status_changed_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=20, default="FIELD_INSPECTION")  # FIELD_INSPECTION | COMPLAINT | DRONE | COURT | OTHER
    complaint_ref = models.CharField(max_length=80, blank=True)
    priority = models.CharField(max_length=10, default="NORMAL")            # LOW | NORMAL | HIGH | URGENT

    # ---- property identification ----
    pid = models.CharField(max_length=40, blank=True, db_index=True, help_text="DULB Property ID")
    pid_snapshot = models.JSONField(default=dict, blank=True, help_text="Property record fetched from the PID API at creation")
    pid_linked_mobile = models.CharField(max_length=15, blank=True)
    alternate_mobile = models.CharField(max_length=15, blank=True)
    address_line = models.TextField()
    locality = models.CharField(max_length=160, blank=True)
    sector = models.CharField(max_length=60, blank=True)
    village_colony = models.CharField(max_length=160, blank=True)
    pincode = models.CharField(max_length=6, blank=True)
    ward = models.ForeignKey(Ward, null=True, blank=True, on_delete=models.SET_NULL, related_name="cases")
    zone = models.ForeignKey(Zone, null=True, blank=True, on_delete=models.SET_NULL, related_name="cases")
    division = models.ForeignKey(Division, null=True, blank=True, on_delete=models.SET_NULL, related_name="cases")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    location_accuracy_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    land_type = models.CharField(max_length=12, choices=LandType.choices, default=LandType.UNKNOWN)
    govt_parcel = models.ForeignKey(GovtLandParcel, null=True, blank=True, on_delete=models.SET_NULL, related_name="cases")
    sanctioned_plan = models.ForeignKey(SanctionedPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="cases")

    # ---- persons ----
    owner_name = models.CharField(max_length=200, blank=True)
    owner_father_name = models.CharField(max_length=200, blank=True)
    occupier_name = models.CharField(max_length=200, blank=True)
    builder_name = models.CharField(max_length=200, blank=True)
    person_on_site = models.CharField(max_length=200, blank=True)

    # ---- construction particulars ----
    construction_stage = models.CharField(max_length=20, choices=ConstructionStage.choices, default=ConstructionStage.UNDER_CONSTRUCTION)
    plot_area_sqm = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    covered_area_sqm = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    storeys = models.CharField(max_length=40, blank=True)
    height_m = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    use_observed = models.CharField(max_length=80, blank=True)
    description = models.TextField(help_text="Inspection report / observations")
    measurements = models.JSONField(default=dict, blank=True, help_text="Permitted vs actual values")

    # ---- workflow ownership ----
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bvms_reported_cases")
    assigned_ae = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="bvms_ae_cases")
    assigned_jc = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="bvms_jc_cases")
    current_owner_role = models.CharField(max_length=24, choices=Role.choices, default=Role.JE)
    stage_due_at = models.DateTimeField(null=True, blank=True, help_text="SLA due time for the current stage")
    sla_breached = models.BooleanField(default=False)

    # ---- key dates ----
    inspected_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    ae_forwarded_at = models.DateTimeField(null=True, blank=True)
    jc_received_at = models.DateTimeField(null=True, blank=True)
    scn_issued_at = models.DateTimeField(null=True, blank=True)
    scn_served_at = models.DateTimeField(null=True, blank=True)
    response_due_at = models.DateTimeField(null=True, blank=True)
    response_received_at = models.DateTimeField(null=True, blank=True)
    hearing_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    order_issued_at = models.DateTimeField(null=True, blank=True)
    order_served_at = models.DateTimeField(null=True, blank=True)
    compliance_due_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    # ---- outcome ----
    stop_work_issued = models.BooleanField(default=False)
    sealed = models.BooleanField(default=False)
    decision = models.CharField(max_length=30, blank=True)   # DEMOLITION | SEALING | ALTERATION | VACATE | DROP | REGULARISE | REFER | EVICTION
    decision_reasons = models.TextField(blank=True)
    final_order = models.ForeignKey("Notice", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    closure_reason = models.TextField(blank=True)
    demolition_cost_inr = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cost_recovery_status = models.CharField(max_length=20, blank=True)   # PENDING | DEMANDED | RECOVERED | WAIVED

    class Meta:
        db_table = "bvms_case"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "zone"]),
            models.Index(fields=["ward", "status"]),
            models.Index(fields=["land_type"]),
            models.Index(fields=["compliance_due_at"]),
            models.Index(fields=["response_due_at"]),
        ]

    def __str__(self):
        return self.case_no

    # convenience
    @property
    def point(self):
        if self.latitude is None or self.longitude is None:
            return None
        return (float(self.longitude), float(self.latitude))


class CaseViolation(models.Model):
    case = models.ForeignKey(ViolationCase, on_delete=models.CASCADE, related_name="violations")
    violation_type = models.ForeignKey(ViolationType, on_delete=models.PROTECT)
    details = models.JSONField(default=dict, blank=True, help_text="permitted / actual measurements, floors etc.")
    remarks = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "bvms_case_violation"
        unique_together = ("case", "violation_type")


class Notice(TimeStamped):
    """A show-cause notice, order, memo or referral generated for a case."""
    class SignatureStatus(models.TextChoices):
        UNSIGNED = "UNSIGNED", "Unsigned"
        SIGNED = "SIGNED", "Digitally signed"
        FAILED = "FAILED", "Signing failed"

    class ServiceMode(models.TextChoices):
        SMS = "SMS", "SMS to registered mobile"
        IN_PERSON = "IN_PERSON", "Delivered in person"
        AFFIXATION = "AFFIXATION", "Affixed on premises"
        POST = "POST", "Registered post / speed post"
        EMAIL = "EMAIL", "E-mail"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        BEAT_OF_DRUM = "BEAT_OF_DRUM", "Beat of drum / public announcement"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(ViolationCase, on_delete=models.CASCADE, related_name="notices")
    order_type = models.ForeignKey(OrderType, on_delete=models.PROTECT)
    notice_no = models.CharField(max_length=60, unique=True, db_index=True)
    kind = models.CharField(max_length=12)                          # copied from order_type.kind
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bvms_issued_notices")
    issued_at = models.DateTimeField(default=timezone.now)
    addressee_name = models.CharField(max_length=200)
    addressee_address = models.TextField(blank=True)
    addressee_mobiles = models.JSONField(default=list)             # ["98xxxxxxxx", ...]
    response_days = models.PositiveSmallIntegerField(default=0)
    response_due_at = models.DateTimeField(null=True, blank=True)
    compliance_days = models.PositiveSmallIntegerField(default=0)
    compliance_due_at = models.DateTimeField(null=True, blank=True)
    hearing_at = models.DateTimeField(null=True, blank=True)
    hearing_venue = models.CharField(max_length=200, blank=True)
    operative_text_en = models.TextField(blank=True)
    operative_text_hi = models.TextField(blank=True)
    html_snapshot = models.TextField(blank=True)
    context_snapshot = models.JSONField(default=dict, blank=True)
    pdf = models.FileField(upload_to=notice_pdf_path, null=True, blank=True)
    signed_pdf = models.FileField(upload_to=notice_pdf_path, null=True, blank=True)
    document_hash = models.CharField(max_length=64, blank=True, db_index=True)
    verification_code = models.CharField(max_length=24, unique=True, db_index=True)
    qr_payload = models.TextField(blank=True)
    signature_status = models.CharField(max_length=10, choices=SignatureStatus.choices, default=SignatureStatus.UNSIGNED)
    signer_name = models.CharField(max_length=200, blank=True)
    signer_cert_subject = models.CharField(max_length=300, blank=True)
    signer_cert_serial = models.CharField(max_length=120, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    signature_error = models.TextField(blank=True)
    # service
    served_at = models.DateTimeField(null=True, blank=True)
    served_mode = models.CharField(max_length=16, choices=ServiceMode.choices, blank=True)
    served_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    service_remarks = models.TextField(blank=True)
    superseded_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    is_final_order = models.BooleanField(default=False)

    class Meta:
        db_table = "bvms_notice"
        ordering = ["-issued_at"]

    def __str__(self):
        return self.notice_no


class NoticeDispatch(TimeStamped):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name="dispatches")
    channel = models.CharField(max_length=10, default="SMS")     # SMS | WHATSAPP | EMAIL
    to = models.CharField(max_length=120)
    message = models.TextField()
    status = models.CharField(max_length=12, default="QUEUED")   # QUEUED | SENT | DELIVERED | FAILED
    provider_ref = models.CharField(max_length=120, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bvms_notice_dispatch"


class CaseResponse(TimeStamped):
    """Reply of the noticee to a show-cause notice."""
    class ReceivedVia(models.TextChoices):
        JE = "JE", "Uploaded by JE (field)"
        JC_CLERK = "JC_CLERK", "Uploaded by JC office clerk"
        AE = "AE", "Uploaded by AE"
        JC = "JC", "Uploaded by JC"
        HEARING = "HEARING", "Submitted at hearing"
        POST = "POST", "Received by post / dak"

    case = models.ForeignKey(ViolationCase, on_delete=models.CASCADE, related_name="responses")
    notice = models.ForeignKey(Notice, null=True, blank=True, on_delete=models.SET_NULL, related_name="responses")
    received_on = models.DateField()
    received_via = models.CharField(max_length=10, choices=ReceivedVia.choices)
    submitted_by_name = models.CharField(max_length=200, blank=True)
    summary = models.TextField()
    requests_hearing = models.BooleanField(default=False)
    is_within_time = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    ae_comments = models.TextField(blank=True)
    ae_commented_at = models.DateTimeField(null=True, blank=True)
    jc_remarks = models.TextField(blank=True)

    class Meta:
        db_table = "bvms_case_response"
        ordering = ["-received_on"]


class Hearing(TimeStamped):
    case = models.ForeignKey(ViolationCase, on_delete=models.CASCADE, related_name="hearings")
    notice = models.ForeignKey(Notice, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    scheduled_at = models.DateTimeField()
    venue = models.CharField(max_length=200, blank=True)
    presiding = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    held_at = models.DateTimeField(null=True, blank=True)
    attendees = models.TextField(blank=True)
    proceedings = models.TextField(blank=True)
    outcome = models.CharField(max_length=30, blank=True)   # ADJOURNED | HEARD | EX_PARTE
    next_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bvms_hearing"
        ordering = ["-scheduled_at"]


class Appeal(TimeStamped):
    case = models.ForeignKey(ViolationCase, on_delete=models.CASCADE, related_name="appeals")
    order = models.ForeignKey(Notice, null=True, blank=True, on_delete=models.SET_NULL, related_name="appeals")
    filed_on = models.DateField()
    authority = models.CharField(max_length=200)            # Divisional Commissioner / Commissioner / High Court
    appeal_no = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=16, default="PENDING")   # PENDING | STAYED | DISMISSED | ALLOWED | MODIFIED | WITHDRAWN
    stay_granted = models.BooleanField(default=False)
    stay_until = models.DateField(null=True, blank=True)
    conditions = models.TextField(blank=True)               # e.g. bank guarantee under s.263A(4)
    decided_on = models.DateField(null=True, blank=True)
    decision_summary = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        db_table = "bvms_appeal"


class ExecutionRecord(TimeStamped):
    class Mode(models.TextChoices):
        OWNER_SELF = "OWNER_SELF", "Complied by owner"
        CORPORATION = "CORPORATION", "Executed by the Corporation"

    class Action(models.TextChoices):
        DEMOLITION = "DEMOLITION", "Demolition"
        PARTIAL_DEMOLITION = "PARTIAL_DEMOLITION", "Partial demolition"
        SEALING = "SEALING", "Sealing"
        DESEALING = "DESEALING", "De-sealing"
        EVICTION = "EVICTION", "Eviction / possession taken"
        REMOVAL = "REMOVAL", "Removal of encroachment"
        ALTERATION = "ALTERATION", "Alteration carried out"

    case = models.ForeignKey(ViolationCase, on_delete=models.CASCADE, related_name="executions")
    order = models.ForeignKey(Notice, null=True, blank=True, on_delete=models.SET_NULL, related_name="executions")
    action = models.CharField(max_length=20, choices=Action.choices)
    mode = models.CharField(max_length=12, choices=Mode.choices)
    executed_on = models.DateTimeField()
    squad_incharge = models.CharField(max_length=200, blank=True)
    police_assistance = models.BooleanField(default=False)
    police_station = models.CharField(max_length=120, blank=True)
    duty_magistrate = models.CharField(max_length=200, blank=True)
    machinery_used = models.CharField(max_length=300, blank=True)
    area_demolished_sqm = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    seal_memo_no = models.CharField(max_length=60, blank=True)
    cost_incurred_inr = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bvms_execution"
        ordering = ["-executed_on"]


# ============================================================================
# 6. Audit trail (hash-chained) and notifications
# ============================================================================
class CaseEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    case = models.ForeignKey(ViolationCase, on_delete=models.CASCADE, related_name="events")
    at = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_role = models.CharField(max_length=24, blank=True)
    action = models.CharField(max_length=40)                 # CREATE, SUBMIT_TO_AE, AE_FORWARD, JC_ISSUE_NOTICE ...
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    remarks = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_id = models.CharField(max_length=120, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    prev_hash = models.CharField(max_length=64, blank=True)
    hash = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        db_table = "bvms_case_event"
        ordering = ["at", "id"]

    def compute_hash(self) -> str:
        body = json.dumps({
            "case": str(self.case_id), "at": self.at.isoformat(), "actor": self.actor_id,
            "action": self.action, "from": self.from_status, "to": self.to_status,
            "remarks": self.remarks, "payload": self.payload, "prev": self.prev_hash,
        }, sort_keys=True, default=str)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


class Notification(TimeStamped):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bvms_notifications")
    case = models.ForeignKey(ViolationCase, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    level = models.CharField(max_length=10, default="INFO")   # INFO | WARNING | ESCALATION
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bvms_notification"
        ordering = ["-created_at"]


class OTPRequest(models.Model):
    """Standalone-mode OTP login (the platform's own OTP service is used when mounted inside sms-be)."""
    mobile = models.CharField(max_length=15, db_index=True)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bvms_otp"
