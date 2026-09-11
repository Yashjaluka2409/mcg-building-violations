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
    BRANCH_OFFICER = "BRANCH_OFFICER", "Branch officer (Planning / Revenue / Legal ...) - consulted on cases"
    GIS_LAB = "GIS_LAB", "GIS lab - maintains government-land and ward layers"
    ADMIN = "ADMIN", "Module administrator"
    VIEWER = "VIEWER", "Read-only (MIS)"


class Branch(models.Model):
    """A branch of the Corporation that can be consulted on a case (Planning, Revenue, Legal, Fire ...).
    Admin-editable; branch officers see only the cases referred to their branch."""
    code = models.CharField(max_length=20, primary_key=True)     # PLANNING, REVENUE, LEGAL ...
    name_en = models.CharField(max_length=120)
    name_hi = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    head_designation = models.CharField(max_length=120, blank=True)   # e.g. District Town Planner (MCG)
    default_response_days = models.PositiveSmallIntegerField(default=7)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "bvms_branch"
        ordering = ["code"]

    def __str__(self):
        return self.name_en


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
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name="officers",
                               help_text="For BRANCH_OFFICER: the branch this officer answers for")
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
    LEGACY_ORDER = "LEGACY_ORDER", "Scanned copy of an order issued before the system"
    OTHER = "OTHER", "Other"


class LandLayerUpload(TimeStamped):
    """One upload of a government-land layer by the GIS lab (GeoJSON / KML / zipped shapefile, WGS84).
    Uploading again with the same `layer_key` creates a new version and retires the previous parcels."""
    class Format(models.TextChoices):
        GEOJSON = "GEOJSON", "GeoJSON"
        KML = "KML", "KML / KMZ"
        SHP_ZIP = "SHP_ZIP", "Zipped shapefile"

    name = models.CharField(max_length=200)
    layer_key = models.SlugField(max_length=80, db_index=True, default="", help_text="Stable id of the layer, e.g. mcg-green-belts; re-uploads with the same key replace the old version")
    version = models.PositiveIntegerField(default=1)
    replaces = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replaced_by")
    agency = models.CharField(max_length=20, choices=LandOwningAgency.choices)
    source_file = models.FileField(upload_to="bvms/land-layers/")
    file_format = models.CharField(max_length=10, choices=Format.choices, default=Format.GEOJSON)
    source = models.CharField(max_length=200, blank=True, default="", help_text="Revenue record / survey / drone / DTP layout ...")
    survey_date = models.DateField(null=True, blank=True)
    feature_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    remarks = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)
    import_log = models.TextField(blank=True, default="")

    class Meta:
        db_table = "bvms_land_layer_upload"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.layer_key} v{self.version}"


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
    layer_key = models.SlugField(max_length=80, blank=True, default="", db_index=True)
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
    APPEAL = "APPEAL", "Appeal memo / pleadings"
    STAY_ORDER = "STAY_ORDER", "Stay / interim order of the appellate authority or court"
    COURT_ORDER = "COURT_ORDER", "Final order / judgment"
    SANCTION_DOC = "SANCTION_DOC", "Sanction / licence document"
    TASK_EVIDENCE = "TASK_EVIDENCE", "Planned-inspection evidence (no violation / not found)"
    BRANCH_REFERRAL = "BRANCH_REFERRAL", "Document sent with a branch referral"
    BRANCH_RESPONSE = "BRANCH_RESPONSE", "Branch response / report"
    OTHER = "OTHER", "Other"


class MediaAttachment(TimeStamped):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey("ViolationCase", null=True, blank=True, on_delete=models.CASCADE, related_name="media")
    task = models.ForeignKey("InspectionTask", null=True, blank=True, on_delete=models.SET_NULL, related_name="media")
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
    # Anti-spoofing verdict for the geotag (see services/location_integrity.py): PASS | FLAGGED | UNVERIFIED (no geotag)
    integrity_status = models.CharField(max_length=12, default="UNVERIFIED", db_index=True)
    integrity_check = models.ForeignKey("LocationIntegrityCheck", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
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
    source = models.CharField(max_length=20, default="FIELD_INSPECTION")  # FIELD_INSPECTION | COMPLAINT | DRONE | COURT | LEGACY_ORDER | OTHER
    legacy_reference = models.CharField(max_length=120, blank=True, help_text="Register / file reference of an order issued before the system")
    legacy_batch = models.ForeignKey("LegacyOrderBatch", null=True, blank=True, on_delete=models.SET_NULL, related_name="cases")
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

    # ---- planned inspection (if the case was created from a task pushed by the JC) ----
    task = models.OneToOneField("InspectionTask", null=True, blank=True, on_delete=models.SET_NULL, related_name="case")
    inspector_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, help_text="Officer's device location at the time of recording")
    inspector_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    inspector_distance_m = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # ---- litigation flag (mirrors the latest Appeal so lists / dashboards can filter) ----
    litigation_status = models.CharField(max_length=20, default="NONE", db_index=True)   # NONE | APPEAL_PENDING | STAYED | DECIDED
    litigation_authority = models.CharField(max_length=30, blank=True)                   # DIVISIONAL_COMMISSIONER | HIGH_COURT | SUPREME_COURT ...
    stay_until = models.DateField(null=True, blank=True)
    next_hearing_on = models.DateField(null=True, blank=True)

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
    is_legacy = models.BooleanField(default=False, help_text="Issued on paper before the system; original number / date / signatory kept, scanned copy attached")

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
    """An appeal / writ / suit against a notice or order, and the stay (if any) granted in it.
    A stay is recorded only with the stay order uploaded to the case file, so that every deferred
    action has a legal backing on record."""
    class Authority(models.TextChoices):
        DIVISIONAL_COMMISSIONER = "DIVISIONAL_COMMISSIONER", "Divisional Commissioner, Gurugram (s.261(2) / s.263A(4))"
        COMMISSIONER_MCG = "COMMISSIONER_MCG", "Commissioner, MCG (s.408B)"
        CIVIL_COURT = "CIVIL_COURT", "Civil Court / District Court"
        HIGH_COURT = "HIGH_COURT", "Punjab & Haryana High Court"
        SUPREME_COURT = "SUPREME_COURT", "Supreme Court of India"
        NGT = "NGT", "National Green Tribunal"
        OTHER = "OTHER", "Other forum"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending - no stay"
        STAYED = "STAYED", "Stay / status quo granted"
        STAY_VACATED = "STAY_VACATED", "Stay vacated"
        DISMISSED = "DISMISSED", "Dismissed"
        ALLOWED = "ALLOWED", "Allowed (order set aside)"
        MODIFIED = "MODIFIED", "Order modified"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"
        DISPOSED = "DISPOSED", "Disposed with directions"

    class StayScope(models.TextChoices):
        FULL = "FULL", "All action stayed"
        DEMOLITION_ONLY = "DEMOLITION_ONLY", "Demolition stayed (sealing / stop-work continue)"
        STATUS_QUO = "STATUS_QUO", "Status quo (no construction, no demolition)"
        PARTIAL = "PARTIAL", "Partial - see conditions"

    case = models.ForeignKey(ViolationCase, on_delete=models.CASCADE, related_name="appeals")
    order = models.ForeignKey(Notice, null=True, blank=True, on_delete=models.SET_NULL, related_name="appeals")
    authority = models.CharField(max_length=30, choices=Authority.choices)
    authority_other = models.CharField(max_length=200, blank=True)
    filed_on = models.DateField()
    appeal_no = models.CharField(max_length=120, blank=True, help_text="Appeal / CWP / SLP / OA number")
    appellant_name = models.CharField(max_length=200, blank=True)
    counsel_for_mcg = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    stay_granted = models.BooleanField(default=False)
    stay_order_date = models.DateField(null=True, blank=True)
    stay_until = models.DateField(null=True, blank=True, help_text="Blank = until further orders / next date")
    stay_scope = models.CharField(max_length=20, choices=StayScope.choices, blank=True)
    stay_order = models.ForeignKey(MediaAttachment, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", help_text="Uploaded copy of the stay / interim order")
    conditions = models.TextField(blank=True)               # e.g. bank guarantee under s.263A(4), no further construction
    next_hearing_on = models.DateField(null=True, blank=True)
    decided_on = models.DateField(null=True, blank=True)
    decision_summary = models.TextField(blank=True)
    final_order = models.ForeignKey(MediaAttachment, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", help_text="Uploaded copy of the final order / judgment")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        db_table = "bvms_appeal"
        ordering = ["-filed_on", "-id"]

    @property
    def is_stay_active(self) -> bool:
        from django.utils import timezone as _tz
        return self.status == self.Status.STAYED and (self.stay_until is None or self.stay_until >= _tz.localdate())


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


# ============================================================================
# 7. Branch referrals (consultation with Planning / Revenue / Legal ...)
# ============================================================================
class BranchReferral(TimeStamped):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Awaiting branch response"
        RESPONDED = "RESPONDED", "Response received"
        CLOSED = "CLOSED", "Closed by referring officer"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    case = models.ForeignKey(ViolationCase, on_delete=models.CASCADE, related_name="referrals")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="referrals")
    referred_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bvms_referrals_made")
    referred_at = models.DateTimeField(default=timezone.now)
    query = models.TextField(help_text="What the branch is asked to examine / report on")
    due_at = models.DateTimeField(null=True, blank=True)
    hold_case = models.BooleanField(default=False, help_text="If true, final orders are blocked until the branch responds (subject to workflow setting)")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="bvms_referrals_assigned")
    response = models.TextField(blank=True)
    recommendation = models.CharField(max_length=40, blank=True)   # e.g. VIOLATION_CONFIRMED / NO_VIOLATION / REGULARISABLE / GOVT_LAND_CONFIRMED / PRIVATE_LAND
    responded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="bvms_referrals_answered")
    responded_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)
    closing_remarks = models.TextField(blank=True)

    class Meta:
        db_table = "bvms_branch_referral"
        ordering = ["-referred_at"]

    def __str__(self):
        return f"{self.case_id} -> {self.branch_id}"


# ============================================================================
# 8. Admin-configurable workflow, permissions and audit of admin changes
# ============================================================================
class WorkflowRule(models.Model):
    """Which role may perform which action when a case is in a given status.
    status "*" = any status. Seeded from the defaults in services/access.py; edited by the admin."""
    status = models.CharField(max_length=30)      # CaseStatus value or "*"
    role = models.CharField(max_length=24, choices=Role.choices)
    action = models.CharField(max_length=40)
    allowed = models.BooleanField(default=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bvms_workflow_rule"
        unique_together = ("status", "role", "action")


class WorkflowSetting(models.Model):
    """Typed key/value settings that change the routing and guards of the workflow."""
    key = models.CharField(max_length=60, primary_key=True)
    value = models.JSONField()
    value_type = models.CharField(max_length=10, default="bool")   # bool | int | str | choice
    label = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    group = models.CharField(max_length=40, default="Routing")
    choices = models.JSONField(default=list, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bvms_workflow_setting"
        ordering = ["group", "key"]


class RolePermission(models.Model):
    """Module-level permissions per role (view all zones, export reports, manage plans ...)."""
    role = models.CharField(max_length=24, choices=Role.choices)
    permission = models.CharField(max_length=40)
    allowed = models.BooleanField(default=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bvms_role_permission"
        unique_together = ("role", "permission")


class OfficerPermissionOverride(models.Model):
    """Grant or revoke a permission for one officer, over and above the role defaults."""
    profile = models.ForeignKey(OfficerProfile, on_delete=models.CASCADE, related_name="permission_overrides")
    permission = models.CharField(max_length=40)
    allowed = models.BooleanField(default=True)
    reason = models.CharField(max_length=300, blank=True)
    order_reference = models.CharField(max_length=120, blank=True, help_text="Office order / Commissioner's order authorising the change")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bvms_officer_permission_override"
        unique_together = ("profile", "permission")


class AdminAuditLog(models.Model):
    """Every administrative change (officer, jurisdiction, rule, permission, setting, re-assignment)."""
    id = models.BigAutoField(primary_key=True)
    at = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=40)          # OFFICER_CREATE, OFFICER_UPDATE, RULES_UPDATE, PERMISSIONS_UPDATE, SETTING_UPDATE, CASES_REASSIGN, BRANCH_UPDATE
    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.CharField(max_length=60, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    order_reference = models.CharField(max_length=120, blank=True)
    remarks = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "bvms_admin_audit_log"
        ordering = ["-at"]


# ============================================================================
# 9. Planned inspections (JC pushes PIDs / map points to the field)
# ============================================================================
class InspectionBatch(TimeStamped):
    """A bulk push of properties for verification, e.g. 'all PGs in the PID database, Zone 2'."""
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=40, default="VERIFICATION")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    source_file = models.FileField(upload_to="bvms/inspection-batches/", null=True, blank=True)
    instructions = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    total = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "bvms_inspection_batch"
        ordering = ["-created_at"]


class InspectionTask(TimeStamped):
    class Status(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        UNASSIGNED = "UNASSIGNED", "Awaiting assignment"
        IN_PROGRESS = "IN_PROGRESS", "Inspection started on site"
        VIOLATION_RECORDED = "VIOLATION_RECORDED", "Violation recorded (case created)"
        NO_VIOLATION = "NO_VIOLATION", "Inspected - no violation"
        NOT_FOUND = "NOT_FOUND", "Property not traceable"
        CANCELLED = "CANCELLED", "Cancelled"

    class Category(models.TextChoices):
        VERIFICATION = "VERIFICATION", "Routine verification"
        PG_HOSTEL = "PG_HOSTEL", "Paying guest / hostel check"
        COMPLAINT = "COMPLAINT", "Complaint verification"
        DRONE_FLAG = "DRONE_FLAG", "Drone / satellite change detection"
        COURT_DIRECTION = "COURT_DIRECTION", "Court / appellate direction"
        SANCTION_FOLLOWUP = "SANCTION_FOLLOWUP", "Sanctioned plan follow-up (DPC / completion)"
        GOVT_LAND = "GOVT_LAND", "Government land watch"
        RE_INSPECTION = "RE_INSPECTION", "Re-inspection of an existing case"
        OTHER = "OTHER", "Other"

    batch = models.ForeignKey(InspectionBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    category = models.CharField(max_length=24, choices=Category.choices, default=Category.VERIFICATION)
    pid = models.CharField(max_length=40, blank=True, db_index=True)
    pid_snapshot = models.JSONField(default=dict, blank=True)
    address = models.TextField(blank=True)
    owner_name = models.CharField(max_length=200, blank=True)
    owner_mobile = models.CharField(max_length=15, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    ward = models.ForeignKey(Ward, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    zone = models.ForeignKey(Zone, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    instructions = models.TextField(blank=True, help_text="What the field officer must check")
    priority = models.CharField(max_length=10, default="NORMAL")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bvms_tasks_created")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="bvms_tasks")
    assigned_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNASSIGNED, db_index=True)
    related_case = models.ForeignKey(ViolationCase, null=True, blank=True, on_delete=models.SET_NULL, related_name="follow_up_tasks", help_text="For re-inspection tasks")
    started_at = models.DateTimeField(null=True, blank=True)
    start_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    start_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    start_distance_m = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    outcome_remarks = models.TextField(blank=True)
    geofence_m = models.PositiveIntegerField(default=100, help_text="Officer must be within this many metres of the point to start")

    class Meta:
        db_table = "bvms_inspection_task"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["assigned_to", "status"]), models.Index(fields=["status", "zone"])]

    def __str__(self):
        return f"Task {self.id} {self.pid or self.address[:30]}"


# ============================================================================
# 13. Location integrity (anti-GPS-spoofing) - see services/location_integrity.py
# ============================================================================
class LocationIntegrityCheck(models.Model):
    """One row per device location the server was asked to trust (evidence upload, inspection recorded,
    planned inspection started/closed, app pre-check). Rejected attempts stay on record as incidents."""

    class Decision(models.TextChoices):
        PASS = "PASS", "Pass"
        FLAGGED = "FLAGGED", "Flagged"
        REJECTED = "REJECTED", "Rejected"

    class Context(models.TextChoices):
        PRECHECK = "PRECHECK", "Pre-check"
        MEDIA_UPLOAD = "MEDIA_UPLOAD", "Evidence upload"
        CASE_CREATE = "CASE_CREATE", "Inspection recorded"
        TASK_START = "TASK_START", "Planned inspection started"
        TASK_CLOSE = "TASK_CLOSE", "Planned inspection closed"

    id = models.BigAutoField(primary_key=True)
    at = models.DateTimeField(default=timezone.now, db_index=True)
    officer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    context = models.CharField(max_length=14, choices=Context.choices)
    decision = models.CharField(max_length=10, choices=Decision.choices, db_index=True)
    reasons = models.JSONField(default=list, blank=True)     # codes that blocked
    flags = models.JSONField(default=list, blank=True)       # codes that only flagged
    case = models.ForeignKey("ViolationCase", null=True, blank=True, on_delete=models.SET_NULL, related_name="integrity_checks")
    task = models.ForeignKey("InspectionTask", null=True, blank=True, on_delete=models.SET_NULL, related_name="integrity_checks")
    media = models.ForeignKey("MediaAttachment", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # the fix
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    accuracy_m = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    altitude_m = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    speed_mps = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    heading = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    provider = models.CharField(max_length=30, blank=True)               # gps | fused | network | web ...
    fix_at = models.DateTimeField(null=True, blank=True, db_index=True)   # device timestamp of the fix
    fix_age_s = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    jitter_m = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    # the device
    device_id = models.CharField(max_length=120, blank=True)
    platform = models.CharField(max_length=10, blank=True)               # ios | android | web
    source = models.CharField(max_length=10, blank=True)                 # app | web | unknown
    app_version = models.CharField(max_length=40, blank=True)
    build_number = models.CharField(max_length=40, blank=True)
    os_version = models.CharField(max_length=40, blank=True)
    device_model = models.CharField(max_length=80, blank=True)
    native_module = models.BooleanField(default=False)                   # native anti-spoofing module was available
    is_physical_device = models.BooleanField(null=True, blank=True)
    mock_location = models.BooleanField(null=True, blank=True)
    rooted = models.BooleanField(null=True, blank=True)
    developer_options = models.BooleanField(null=True, blank=True)
    vpn_active = models.BooleanField(null=True, blank=True)
    proxy_configured = models.BooleanField(null=True, blank=True)
    simulated_by_software = models.BooleanField(null=True, blank=True)   # iOS CLLocationSourceInformation
    produced_by_accessory = models.BooleanField(null=True, blank=True)
    attestation_type = models.CharField(max_length=20, blank=True)       # play_integrity | app_attest
    attestation_status = models.CharField(max_length=12, default="NONE") # NONE | VALID | INVALID | UNSUPPORTED | ERROR
    attestation_detail = models.JSONField(default=dict, blank=True)
    # server-side
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    ip_intel = models.JSONField(default=dict, blank=True)
    ip_distance_km = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    previous = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    travel_distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    travel_speed_kmph = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True)
    signals = models.JSONField(default=dict, blank=True)                 # raw payload from the client

    class Meta:
        db_table = "bvms_location_integrity"
        ordering = ["-at"]
        indexes = [models.Index(fields=["officer", "at"]), models.Index(fields=["decision", "at"])]

    def __str__(self):
        return f"{self.get_context_display()} {self.decision} {self.at:%Y-%m-%d %H:%M}"


class IntegrityNonce(models.Model):
    """Single-use server nonce that binds a Play Integrity / App Attest attestation to one capture."""
    nonce = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bvms_integrity_nonce"


class AppAttestKey(models.Model):
    """Public key attested by Apple App Attest for one officer's device (key id = base64 sha256 of the key)."""
    key_id = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    public_key_pem = models.TextField()
    counter = models.PositiveBigIntegerField(default=0)
    environment = models.CharField(max_length=12, default="production")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bvms_app_attest_key"


# ============================================================================
# 14. Orders issued before the system (legacy register imports) - services/legacy.py
# ============================================================================
class LegacyOrderBatch(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=200)
    source_file = models.FileField(upload_to="bvms/legacy/%Y/%m/", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    total_rows = models.PositiveIntegerField(default=0)
    imported = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "bvms_legacy_batch"
        ordering = ["-created_at"]
