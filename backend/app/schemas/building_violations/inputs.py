"""Input schemas (Pydantic v2) - the request bodies accepted by the API, one for one with the DRF input
serializers of the Django edition. Foreign keys arrive as ids and are resolved in the routers."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Optional
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.timeutil import make_aware_local
from app.models import building_violations as m

LocalDT = Annotated[datetime, AfterValidator(make_aware_local)]      # naive datetimes are local (Asia/Kolkata), as DRF did
Lat = Optional[Decimal]
Money = Optional[Decimal]

SERVICE_MODES = tuple(m.ServiceMode.values)
RECEIVED_VIA = tuple(m.ReceivedVia.values)
AUTHORITIES = tuple(m.AppealAuthority.values)
APPEAL_STATUSES = tuple(m.AppealStatus.values)
STAY_SCOPES = tuple(m.StayScope.values)
EXEC_ACTIONS = tuple(m.ExecutionAction.values)
EXEC_MODES = tuple(m.ExecutionMode.values)
MEDIA_KINDS = tuple(m.MediaKind.values)
TASK_CATEGORIES = tuple(m.TaskCategory.values)
LAND_TYPES = tuple(c for c, _ in m.LandType.choices)
CONSTRUCTION_STAGES = tuple(c for c, _ in m.ConstructionStage.choices)
PRIORITIES = ("LOW", "NORMAL", "HIGH", "URGENT")
LEGACY_STATUSES = ("ORDER_ISSUED", "ORDER_SERVED", "EXECUTION_DUE", "APPEAL_STAY", "COMPLIED", "EXECUTED", "CLOSED", "REGULARISED", "DROPPED")


class In(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, populate_by_name=True)


def _choice(name: str, choices: tuple, allow_blank: bool = False):
    def check(v):
        if v is None or (allow_blank and v == ""):
            return v
        if v not in choices:
            raise ValueError(f'"{v}" is not a valid choice.')
        return v
    return field_validator(name, mode="after")(check)


def _mobile10(v):
    """Indian mobile number stored as exactly 10 digits. Accepts "+91 98765 43210", "098765 43210" or
    "98765-43210"; anything that does not reduce to 10 digits is rejected. Blank stays blank."""
    if v is None or v == "":
        return v
    digits = "".join(ch for ch in str(v) if ch.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("Enter a 10-digit mobile number (digits only).")
    return digits


Mobile10 = Annotated[str, AfterValidator(_mobile10)]
OptMobile10 = Annotated[Optional[str], AfterValidator(_mobile10)]


# ---------------------------------------------------------------- auth
class OTPRequestIn(In):
    mobile: str


class OTPVerifyIn(In):
    mobile: str
    otp: str
    device_id: str = ""


class TokenRefreshIn(In):
    refresh: str


# ---------------------------------------------------------------- cases
class CaseViolationIn(In):
    code: str
    details: dict | None = None
    remarks: str = ""
    is_primary: bool = False


class CaseCreateIn(In):
    source: str = "FIELD_INSPECTION"
    complaint_ref: str = ""
    priority: str = "NORMAL"
    pid: str = ""
    pid_snapshot: dict | None = None
    pid_linked_mobile: str = ""
    alternate_mobile: Mobile10 = ""
    address_line: str
    locality: str = ""
    sector: str = ""
    village_colony: str = ""
    pincode: str = ""
    ward: int | None = None
    zone: int | None = None
    division: int | None = None
    latitude: Lat = None
    longitude: Lat = None
    location_accuracy_m: Optional[Decimal] = None
    land_type: str = "UNKNOWN"
    sanctioned_plan: int | None = None
    owner_name: str = ""
    owner_father_name: str = ""
    occupier_name: str = ""
    builder_name: str = ""
    person_on_site: str = ""
    construction_stage: str = "UNDER_CONSTRUCTION"
    plot_area_sqm: Optional[Decimal] = None
    covered_area_sqm: Optional[Decimal] = None
    storeys: str = ""
    height_m: Optional[Decimal] = None
    use_observed: str = ""
    description: str
    measurements: dict | None = None
    inspected_at: LocalDT | None = None
    task: int | None = None
    inspector_latitude: Lat = None
    inspector_longitude: Lat = None
    location_integrity: Any = None
    violations: list[CaseViolationIn] = Field(min_length=1)
    media_ids: list[UUID] = []
    submit: bool = False

    _v1 = _choice("priority", PRIORITIES)
    _v2 = _choice("land_type", LAND_TYPES)
    _v3 = _choice("construction_stage", CONSTRUCTION_STAGES)

    @model_validator(mode="after")
    def _pid_or_address(self):
        if not self.pid and not self.address_line:
            raise ValueError("Either PID or address is required")
        return self


class CaseDraftUpdateIn(In):
    """PATCH of a draft: any subset of the case's editable columns."""
    complaint_ref: str | None = None
    priority: str | None = None
    pid: str | None = None
    pid_snapshot: dict | None = None
    pid_linked_mobile: str | None = None
    alternate_mobile: OptMobile10 = None
    address_line: str | None = None
    locality: str | None = None
    sector: str | None = None
    village_colony: str | None = None
    pincode: str | None = None
    ward: int | None = None
    zone: int | None = None
    division: int | None = None
    latitude: Lat = None
    longitude: Lat = None
    location_accuracy_m: Optional[Decimal] = None
    land_type: str | None = None
    sanctioned_plan: int | None = None
    owner_name: str | None = None
    owner_father_name: str | None = None
    occupier_name: str | None = None
    builder_name: str | None = None
    person_on_site: str | None = None
    construction_stage: str | None = None
    plot_area_sqm: Optional[Decimal] = None
    covered_area_sqm: Optional[Decimal] = None
    storeys: str | None = None
    height_m: Optional[Decimal] = None
    use_observed: str | None = None
    description: str | None = None
    measurements: dict | None = None
    inspected_at: LocalDT | None = None
    inspector_latitude: Lat = None
    inspector_longitude: Lat = None
    violations: list[CaseViolationIn] | None = None


class RemarksIn(In):
    remarks: str = ""


class AEForwardIn(RemarksIn):
    jc_user: UUID | None = None
    recommendation: str = ""
    _v = _choice("recommendation", ("SCN", "STOP_WORK", "SEALING", "DEMOLITION", "DROP", "REGULARISE", "REFER"), allow_blank=True)


class IssueNoticeIn(RemarksIn):
    order_type: str
    days: int | None = Field(default=None, ge=0, le=365)
    addressee_name: str = ""
    addressee_address: str = ""
    mobiles: list[str] = []
    hearing_at: LocalDT | None = None
    hearing_venue: str = ""
    operative_text_en: str = ""
    operative_text_hi: str = ""
    send_sms: bool = True
    is_final_order: bool | None = None


class RecordServiceIn(RemarksIn):
    notice: UUID
    mode: str
    served_at: LocalDT | None = None
    media_ids: list[UUID] = []
    _v = _choice("mode", SERVICE_MODES)


class RecordResponseIn(RemarksIn):
    notice: UUID | None = None
    received_on: date
    received_via: str = ""
    submitted_by_name: str = ""
    summary: str
    requests_hearing: bool = False
    media_ids: list[UUID] = []
    _v = _choice("received_via", RECEIVED_VIA, allow_blank=True)


class AECommentIn(In):
    response: int
    comments: str


class ScheduleHearingIn(RemarksIn):
    scheduled_at: LocalDT
    venue: str = "Office of the Joint Commissioner, MCG"
    notice: UUID | None = None


class RecordHearingIn(In):
    hearing: int
    proceedings: str = ""
    attendees: str = ""
    outcome: str = "HEARD"
    next_date: LocalDT | None = None
    media_ids: list[UUID] = []
    _v = _choice("outcome", ("HEARD", "ADJOURNED", "EX_PARTE"))


class RecordAppealIn(RemarksIn):
    filed_on: date
    authority: str
    authority_other: str = ""
    appeal_no: str = ""
    appellant_name: str = ""
    counsel_for_mcg: str = ""
    stay_granted: bool = False
    stay_order_date: date | None = None
    stay_until: date | None = None
    stay_scope: str = ""
    conditions: str = ""
    next_hearing_on: date | None = None
    stay_order_media: UUID | None = None
    order: UUID | None = None
    media_ids: list[UUID] = []
    _v1 = _choice("authority", AUTHORITIES)
    _v2 = _choice("stay_scope", STAY_SCOPES, allow_blank=True)


class UpdateAppealIn(RemarksIn):
    appeal: int
    status: str | None = None
    decided_on: date | None = None
    decision_summary: str = ""
    new_compliance_days: int | None = None
    stay_until: date | None = None
    stay_scope: str | None = None
    conditions: str | None = None
    next_hearing_on: date | None = None
    appeal_no: str | None = None
    counsel_for_mcg: str | None = None
    stay_order_media: UUID | None = None
    final_order_media: UUID | None = None
    media_ids: list[UUID] = []
    _v1 = _choice("status", APPEAL_STATUSES, allow_blank=True)
    _v2 = _choice("stay_scope", STAY_SCOPES, allow_blank=True)


class RecordExecutionIn(RemarksIn):
    action: str
    mode: str
    executed_on: LocalDT
    media_ids: list[UUID]
    squad_incharge: str = ""
    police_assistance: bool = False
    police_station: str = ""
    duty_magistrate: str = ""
    machinery_used: str = ""
    area_demolished_sqm: Optional[Decimal] = None
    seal_memo_no: str = ""
    cost_incurred_inr: Optional[Decimal] = None
    _v1 = _choice("action", EXEC_ACTIONS)
    _v2 = _choice("mode", EXEC_MODES)


class DropIn(In):
    remarks: str = Field(min_length=1)
    regularised: bool = False


class ReferBranchIn(RemarksIn):
    branch: str
    query: str = Field(min_length=1)
    due_days: int | None = Field(default=None, ge=1, le=90)
    hold_case: bool = False
    assigned_to: UUID | None = None
    media_ids: list[UUID] = []


class RespondReferralIn(In):
    referral: int
    response: str = Field(min_length=1)
    recommendation: str = ""
    media_ids: list[UUID] = []
    _v = _choice("recommendation", ("", "VIOLATION_CONFIRMED", "NO_VIOLATION", "REGULARISABLE", "GOVT_LAND_CONFIRMED", "PRIVATE_LAND_CONFIRMED", "OWNERSHIP_DISPUTED", "LEGAL_OK_TO_PROCEED", "LEGAL_HOLD", "FURTHER_INQUIRY"), allow_blank=True)


class CloseReferralIn(RemarksIn):
    referral: int
    withdrawn: bool = False


class ReassignIn(RemarksIn):
    assigned_ae: UUID | None = None
    assigned_jc: UUID | None = None
    reported_by: UUID | None = None
    order_reference: str = ""


class BulkReassignIn(ReassignIn):
    case_ids: list[UUID] = []
    zone: int | None = None
    ward: int | None = None
    from_user: UUID | None = None
    only_open: bool = True


# ---------------------------------------------------------------- officers / admin
class OfficerIn(In):
    user_id: UUID | None = None
    username: str | None = None
    first_name: str = ""
    last_name: str = ""
    role: str | None = None
    designation: str | None = None
    employee_code: str | None = None
    mobile: str | None = None
    email: str | None = None
    zones: list[int] | None = None
    wards: list[int] | None = None
    divisions: list[int] | None = None
    reports_to: int | None = None
    delegation_order_no: str | None = None
    delegation_order_date: date | None = None
    parent_profile: int | None = None
    branch: str | None = None
    active: bool | None = None
    order_reference: str = ""


class BranchIn(In):
    code: str | None = None
    name_en: str | None = None
    name_hi: str | None = None
    description: str | None = None
    head_designation: str | None = None
    default_response_days: int | None = None
    active: bool | None = None
    order_reference: str = ""


class NotificationsMarkReadIn(In):
    ids: list[int] | None = None


class ResendSmsIn(In):
    mobiles: list[str] = []


# ---------------------------------------------------------------- planned inspections
class TaskCreateIn(In):
    pid: str = ""
    address: str = ""
    latitude: Lat = None
    longitude: Lat = None
    category: str = "VERIFICATION"
    instructions: str = ""
    priority: str = "NORMAL"
    assigned_to: UUID | None = None
    due_days: int | None = Field(default=None, ge=1, le=90)
    ward: int | None = None
    owner_name: str = ""
    owner_mobile: str = ""
    related_case: UUID | None = None
    _v1 = _choice("category", TASK_CATEGORIES)
    _v2 = _choice("priority", PRIORITIES)


class TaskUpdateIn(In):
    instructions: str | None = None
    priority: str | None = None
    category: str | None = None
    due_at: LocalDT | None = None
    address: str | None = None
    owner_name: str | None = None
    owner_mobile: str | None = None


class TaskStartIn(In):
    latitude: Decimal
    longitude: Decimal
    accuracy_m: Optional[Decimal] = None
    location_integrity: Any = None


class TaskCloseIn(In):
    outcome: str
    remarks: str = Field(min_length=1)
    media_ids: list[UUID] = []
    latitude: Lat = None
    longitude: Lat = None
    location_integrity: Any = None
    _v = _choice("outcome", ("NO_VIOLATION", "NOT_FOUND"))


class TaskAssignIn(RemarksIn):
    assigned_to: UUID


class TaskCancelIn(RemarksIn):
    pass


# ---------------------------------------------------------------- integrity
class PrecheckIn(In):
    latitude: Lat = None
    longitude: Lat = None
    accuracy_m: Optional[Decimal] = None
    location_integrity: Any = None
    device_id: str = ""


# ---------------------------------------------------------------- legacy orders
class LegacyOrderIn(In):
    """One paper order. Only order_no, order_date and pid-or-address are mandatory; everything else is optional history."""
    order_no: str = Field(max_length=60)
    order_date: date
    order_type: str = "DEMOLITION_ORDER_261"
    issued_by_name: str = ""
    issued_by_designation: str = ""
    scn_no: str = ""
    scn_date: date | None = None
    pid: str = ""
    address_line: str = ""
    locality: str = ""
    sector: str = ""
    village_colony: str = ""
    pincode: str = ""
    ward: int | None = None
    ward_number: int | None = None
    latitude: Lat = None
    longitude: Lat = None
    land_type: str | None = None
    owner_name: str = ""
    owner_father_name: str = ""
    occupier_name: str = ""
    pid_linked_mobile: str = ""
    alternate_mobile: str = ""
    description: str = ""
    violations: list[CaseViolationIn] = []
    compliance_days: int | None = Field(default=None, ge=0)
    compliance_due_on: date | None = None
    served_on: date | None = None
    served_mode: str = ""
    current_status: str = ""
    executed_on: date | None = None
    execution_action: str = ""
    execution_mode: str = ""
    cost_incurred_inr: Optional[Decimal] = None
    area_demolished_sqm: Optional[Decimal] = None
    appeal_authority: str = ""
    authority_other: str = ""
    appeal_no: str = ""
    appellant_name: str = ""
    appeal_filed_on: date | None = None
    stay_granted: bool = False
    stay_order_date: date | None = None
    stay_until: date | None = None
    closed_on: date | None = None
    closure_reason: str = ""
    legacy_reference: str = ""
    remarks: str = ""
    priority: str = ""
    media_ids: list[UUID] = []
    order_reference: str = ""
    _v1 = _choice("land_type", LAND_TYPES, allow_blank=True)
    _v2 = _choice("served_mode", SERVICE_MODES, allow_blank=True)
    _v3 = _choice("current_status", LEGACY_STATUSES, allow_blank=True)
    _v4 = _choice("execution_action", EXEC_ACTIONS, allow_blank=True)
    _v5 = _choice("execution_mode", EXEC_MODES, allow_blank=True)
    _v6 = _choice("appeal_authority", AUTHORITIES, allow_blank=True)


class LegacyStatusUpdateIn(In):
    status: str
    on_date: date | None = None
    remarks: str = ""
    order_reference: str = ""
    served_mode: str = ""
    execution_action: str = ""
    execution_mode: str = ""
    cost_incurred_inr: Optional[Decimal] = None
    area_demolished_sqm: Optional[Decimal] = None
    appeal_authority: str = ""
    appeal_no: str = ""
    appellant_name: str = ""
    stay_order_date: date | None = None
    stay_until: date | None = None
    closure_reason: str = ""
    media_ids: list[UUID] = []
    _v1 = _choice("status", LEGACY_STATUSES)
    _v2 = _choice("served_mode", SERVICE_MODES, allow_blank=True)
    _v3 = _choice("execution_action", EXEC_ACTIONS, allow_blank=True)
    _v4 = _choice("execution_mode", EXEC_MODES, allow_blank=True)
    _v5 = _choice("appeal_authority", AUTHORITIES, allow_blank=True)


# ---------------------------------------------------------------- GIS / sanctioned plans / masters
class GovtParcelIn(In):
    name: str | None = None
    agency: str | None = None
    land_use: str | None = None
    village: str | None = None
    khasra_no: str | None = None
    area_sqm: Optional[Decimal] = None
    ward: int | None = None
    geometry: dict | None = None
    properties: dict | None = None
    active: bool | None = None


class SanctionedPlanIn(In):
    plan_no: str | None = None
    pid: str | None = None
    address: str | None = None
    ward: int | None = None
    zone: int | None = None
    latitude: Lat = None
    longitude: Lat = None
    owner_name: str | None = None
    owner_mobile: str | None = None
    plot_area_sqm: Optional[Decimal] = None
    land_use: str | None = None
    building_type: str | None = None
    sanctioned_on: date | None = None
    valid_till: date | None = None
    sanction_mode: str | None = None
    permitted_floors: str | None = None
    permitted_ground_coverage_pct: Optional[Decimal] = None
    permitted_far: Optional[Decimal] = None
    permitted_height_m: Optional[Decimal] = None
    setbacks: dict | None = None
    licence_no: str | None = None
    licence_holder: str | None = None
    licence_date: date | None = None
    licence_valid_till: date | None = None
    licence_authority: str | None = None
    colony_name: str | None = None
    architect_name: str | None = None
    architect_registration_no: str | None = None
    dpc_certificate_on: date | None = None
    occupation_certificate_no: str | None = None
    occupation_certificate_on: date | None = None
    status: str | None = None
    external_ref: str | None = None
    remarks: str | None = None
