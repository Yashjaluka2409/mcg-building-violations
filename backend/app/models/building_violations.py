"""
Data model of the MCG Building Violation Management System (BVMS) - SQLAlchemy 2.0 edition.

Design notes for the IT team
----------------------------
* All tables are prefixed ``bvms_`` so they sit safely beside the platform's tables; the user table is
  ``users`` (UUID primary key, like the platform's UserModel) - inside the platform the officer profile points at the unified user registry.
* Geometry is stored as GeoJSON in JSON columns (no PostGIS requirement); point-in-polygon tests use shapely.
* Every state change writes a hash-chained ``CaseEvent`` row (tamper-evident audit trail).
* Choice values are plain strings; the ``*_LABELS`` dictionaries carry the display text.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import JSON, BigInteger, Boolean, Column, Date, ForeignKey, Index, Integer, Numeric, String, Table, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import now
from app.db.base import Base, UTCDateTime


def _labels(pairs):
    return {k: v for k, v in pairs}


class UuidPK:
    """UUID primary keys are assigned at construction (as Django did) so the id is usable before the flush."""

    def __init__(self, **kw):
        kw.setdefault("id", uuid.uuid4())
        super().__init__(**kw)


# ============================================================================
# 0. Choice catalogues (display labels)
# ============================================================================
class Role:
    JE, AE, XEN, JC, JC_CLERK = "JE", "AE", "XEN", "JC", "JC_CLERK"
    ADDL_COMMISSIONER, COMMISSIONER, FIELD_STAFF = "ADDL_COMMISSIONER", "COMMISSIONER", "FIELD_STAFF"
    BRANCH_OFFICER, GIS_LAB, ADMIN, VIEWER = "BRANCH_OFFICER", "GIS_LAB", "ADMIN", "VIEWER"
    choices = [("JE", "Junior Engineer (field)"), ("AE", "Assistant Engineer"), ("XEN", "Executive Engineer"), ("JC", "Joint Commissioner"),
               ("JC_CLERK", "JC office clerk (response upload only)"), ("ADDL_COMMISSIONER", "Additional Commissioner"), ("COMMISSIONER", "Commissioner"),
               ("FIELD_STAFF", "Enforcement / demolition squad"), ("BRANCH_OFFICER", "Branch officer (Planning / Revenue / Legal ...) - consulted on cases"),
               ("GIS_LAB", "GIS lab - maintains government-land and ward layers"), ("ADMIN", "Module administrator"), ("VIEWER", "Read-only (MIS)")]


ROLE_LABELS = _labels(Role.choices)


class CaseStatus:
    DRAFT, PENDING_AE, RETURNED_TO_JE, PENDING_JC = "DRAFT", "PENDING_AE", "RETURNED_TO_JE", "PENDING_JC"
    SCN_ISSUED, SCN_SERVED, RESPONSE_RECEIVED = "SCN_ISSUED", "SCN_SERVED", "RESPONSE_RECEIVED"
    RESPONSE_PENDING_AE, RESPONSE_PENDING_JC, NO_RESPONSE = "RESPONSE_PENDING_AE", "RESPONSE_PENDING_JC", "NO_RESPONSE"
    HEARING_SCHEDULED, ORDER_ISSUED, ORDER_SERVED, APPEAL_STAY = "HEARING_SCHEDULED", "ORDER_ISSUED", "ORDER_SERVED", "APPEAL_STAY"
    EXECUTION_DUE, COMPLIED, EXECUTED, CLOSED, DROPPED, REGULARISED = "EXECUTION_DUE", "COMPLIED", "EXECUTED", "CLOSED", "DROPPED", "REGULARISED"
    choices = [("DRAFT", "Draft (JE)"), ("PENDING_AE", "Pending with AE"), ("RETURNED_TO_JE", "Returned to JE for re-inspection"), ("PENDING_JC", "Pending with JC"),
               ("SCN_ISSUED", "Show cause notice issued"), ("SCN_SERVED", "SCN served - response awaited"), ("RESPONSE_RECEIVED", "Response received"),
               ("RESPONSE_PENDING_AE", "Response with AE for comments"), ("RESPONSE_PENDING_JC", "Response with JC for decision"), ("NO_RESPONSE", "No response within time"),
               ("HEARING_SCHEDULED", "Hearing scheduled"), ("ORDER_ISSUED", "Final order issued"), ("ORDER_SERVED", "Order served - compliance period running"),
               ("APPEAL_STAY", "Stayed in appeal"), ("EXECUTION_DUE", "Compliance period over - execution due"), ("COMPLIED", "Complied by owner"),
               ("EXECUTED", "Demolished / sealed by MCG"), ("CLOSED", "Closed"), ("DROPPED", "Dropped - no violation"), ("REGULARISED", "Regularised / compounded")]


STATUS_LABELS = _labels(CaseStatus.choices)
OPEN_EXCLUDE = ["CLOSED", "DROPPED", "REGULARISED"]


class LandType:
    GOVT_MCG, GOVT_STATE, PRIVATE, UNKNOWN = "GOVT_MCG", "GOVT_STATE", "PRIVATE", "UNKNOWN"
    choices = [("GOVT_MCG", "Land vested in MCG"), ("GOVT_STATE", "State Govt / other public land"), ("PRIVATE", "Private land"), ("UNKNOWN", "Not yet determined")]


LAND_TYPE_LABELS = _labels(LandType.choices)


class ConstructionStage:
    choices = [("PLINTH", "Plinth / foundation"), ("UNDER_CONSTRUCTION", "Under construction"), ("COMPLETED", "Completed"), ("OCCUPIED", "Completed and occupied")]


CONSTRUCTION_STAGE_LABELS = _labels(ConstructionStage.choices)


class ViolationCategory:
    choices = [("GOVT_LAND", "Government / Corporation land"), ("PRIVATE_LAND_NO_SANCTION", "Private land - no sanction"), ("DEVIATION_FROM_SANCTION", "Deviation from sanction"),
               ("STREET_ENCROACHMENT", "Street encroachment"), ("MISUSE_CHANGE_OF_USE", "Misuse / change of use"), ("DANGEROUS_UNFIT", "Dangerous / unfit"),
               ("PROCEDURAL_NON_COMPLIANCE", "Non-compliance with orders")]


class LandOwningAgency:
    choices = [("MCG", "Municipal Corporation Gurugram"), ("HSVP", "Haryana Shahari Vikas Pradhikaran"), ("GMDA", "Gurugram Metropolitan Development Authority"),
               ("STATE_GOVT", "State Government (other departments)"), ("PWD", "PWD (B&R)"), ("IRRIGATION", "Irrigation & Water Resources"), ("FOREST", "Forest Department"),
               ("PANCHAYAT", "Gram Panchayat / Shamlat Deh"), ("RAILWAYS", "Railways"), ("NHAI", "NHAI"), ("DEFENCE", "Defence"), ("OTHER", "Other")]


AGENCY_LABELS = _labels(LandOwningAgency.choices)


class MediaKind:
    choices = [("INSPECTION", "Inspection evidence"), ("NOTICE_DELIVERY", "Proof of delivery of notice"), ("ORDER_DELIVERY", "Proof of delivery of order"),
               ("RESPONSE", "Response / reply document"), ("HEARING", "Hearing record"), ("EXECUTION", "Demolition / sealing evidence"), ("COMPLIANCE", "Self-compliance evidence"),
               ("APPEAL", "Appeal memo / pleadings"), ("STAY_ORDER", "Stay / interim order of the appellate authority or court"), ("COURT_ORDER", "Final order / judgment"),
               ("SANCTION_DOC", "Sanction / licence document"), ("TASK_EVIDENCE", "Planned-inspection evidence (no violation / not found)"),
               ("BRANCH_REFERRAL", "Document sent with a branch referral"), ("BRANCH_RESPONSE", "Branch response / report"),
               ("LEGACY_ORDER", "Scanned copy of an order issued before the system"), ("OTHER", "Other")]
    values = [c for c, _ in choices]


class ServiceMode:
    choices = [("SMS", "SMS to registered mobile"), ("IN_PERSON", "Delivered in person"), ("AFFIXATION", "Affixed on premises"), ("POST", "Registered post / speed post"),
               ("EMAIL", "E-mail"), ("WHATSAPP", "WhatsApp"), ("BEAT_OF_DRUM", "Beat of drum / public announcement")]
    values = [c for c, _ in choices]


class SignatureStatus:
    UNSIGNED, SIGNED, FAILED = "UNSIGNED", "SIGNED", "FAILED"


class ReceivedVia:
    choices = [("JE", "Uploaded by JE (field)"), ("JC_CLERK", "Uploaded by JC office clerk"), ("AE", "Uploaded by AE"), ("JC", "Uploaded by JC"), ("HEARING", "Submitted at hearing"), ("POST", "Received by post / dak")]
    values = [c for c, _ in choices]


class AppealAuthority:
    choices = [("DIVISIONAL_COMMISSIONER", "Divisional Commissioner, Gurugram (s.261(2) / s.263A(4))"), ("COMMISSIONER_MCG", "Commissioner, MCG (s.408B)"),
               ("CIVIL_COURT", "Civil Court / District Court"), ("HIGH_COURT", "Punjab & Haryana High Court"), ("SUPREME_COURT", "Supreme Court of India"),
               ("NGT", "National Green Tribunal"), ("OTHER", "Other forum")]
    values = [c for c, _ in choices]


AUTHORITY_LABELS = _labels(AppealAuthority.choices)


class AppealStatus:
    PENDING, STAYED, STAY_VACATED, DISMISSED, ALLOWED, MODIFIED, WITHDRAWN, DISPOSED = "PENDING", "STAYED", "STAY_VACATED", "DISMISSED", "ALLOWED", "MODIFIED", "WITHDRAWN", "DISPOSED"
    choices = [("PENDING", "Pending - no stay"), ("STAYED", "Stay / status quo granted"), ("STAY_VACATED", "Stay vacated"), ("DISMISSED", "Dismissed"),
               ("ALLOWED", "Allowed (order set aside)"), ("MODIFIED", "Order modified"), ("WITHDRAWN", "Withdrawn"), ("DISPOSED", "Disposed with directions")]
    values = [c for c, _ in choices]


APPEAL_STATUS_LABELS = _labels(AppealStatus.choices)


class StayScope:
    FULL = "FULL"
    choices = [("FULL", "All action stayed"), ("DEMOLITION_ONLY", "Demolition stayed (sealing / stop-work continue)"), ("STATUS_QUO", "Status quo (no construction, no demolition)"), ("PARTIAL", "Partial - see conditions")]
    values = [c for c, _ in choices]


class ExecutionMode:
    OWNER_SELF, CORPORATION = "OWNER_SELF", "CORPORATION"
    choices = [("OWNER_SELF", "Complied by owner"), ("CORPORATION", "Executed by the Corporation")]
    values = [c for c, _ in choices]


class ExecutionAction:
    choices = [("DEMOLITION", "Demolition"), ("PARTIAL_DEMOLITION", "Partial demolition"), ("SEALING", "Sealing"), ("DESEALING", "De-sealing"),
               ("EVICTION", "Eviction / possession taken"), ("REMOVAL", "Removal of encroachment"), ("ALTERATION", "Alteration carried out")]
    values = [c for c, _ in choices]


class ReferralStatus:
    PENDING, RESPONDED, CLOSED, WITHDRAWN = "PENDING", "RESPONDED", "CLOSED", "WITHDRAWN"


class TaskStatus:
    ASSIGNED, UNASSIGNED, IN_PROGRESS, VIOLATION_RECORDED, NO_VIOLATION, NOT_FOUND, CANCELLED = "ASSIGNED", "UNASSIGNED", "IN_PROGRESS", "VIOLATION_RECORDED", "NO_VIOLATION", "NOT_FOUND", "CANCELLED"
    choices = [("ASSIGNED", "Assigned"), ("UNASSIGNED", "Awaiting assignment"), ("IN_PROGRESS", "Inspection started on site"), ("VIOLATION_RECORDED", "Violation recorded (case created)"),
               ("NO_VIOLATION", "Inspected - no violation"), ("NOT_FOUND", "Property not traceable"), ("CANCELLED", "Cancelled")]


TASK_STATUS_LABELS = _labels(TaskStatus.choices)


class TaskCategory:
    choices = [("VERIFICATION", "Routine verification"), ("PG_HOSTEL", "Paying guest / hostel check"), ("COMPLAINT", "Complaint verification"),
               ("DRONE_FLAG", "Drone / satellite change detection"), ("COURT_DIRECTION", "Court / appellate direction"), ("SANCTION_FOLLOWUP", "Sanctioned plan follow-up (DPC / completion)"),
               ("GOVT_LAND", "Government land watch"), ("RE_INSPECTION", "Re-inspection of an existing case"), ("OTHER", "Other")]
    values = [c for c, _ in choices]


TASK_CATEGORY_LABELS = _labels(TaskCategory.choices)


class IntegrityContext:
    PRECHECK, MEDIA_UPLOAD, CASE_CREATE, TASK_START, TASK_CLOSE = "PRECHECK", "MEDIA_UPLOAD", "CASE_CREATE", "TASK_START", "TASK_CLOSE"
    choices = [("PRECHECK", "Pre-check"), ("MEDIA_UPLOAD", "Evidence upload"), ("CASE_CREATE", "Inspection recorded"), ("TASK_START", "Planned inspection started"), ("TASK_CLOSE", "Planned inspection closed")]


INTEGRITY_CONTEXT_LABELS = _labels(IntegrityContext.choices)


# ============================================================================
# 1. Users, jurisdiction, officers, legal catalogue
# ============================================================================
class User(UuidPK, Base):
    """User registry of the standalone deployment (UUID primary key like the platform's UserModel; inside the
    platform this table is replaced by the unified user registry and OfficerProfile.user_id points there)."""
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    date_joined: Mapped[datetime] = mapped_column(UTCDateTime, default=now)

    bvms_profile: Mapped[Optional["OfficerProfile"]] = relationship(back_populates="user", uselist=False, lazy="joined", foreign_keys="OfficerProfile.user_id")

    @property
    def pk(self):
        return self.id

    def get_username(self):
        return self.username

    @property
    def is_authenticated(self):
        return True

    def __str__(self):
        return self.username


class Zone(Base):
    __tablename__ = "bvms_zone"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_hi: Mapped[str] = mapped_column(String(80), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Division(Base):
    __tablename__ = "bvms_division"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("bvms_zone.id"))
    name_en: Mapped[str] = mapped_column(String(80), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    zone: Mapped[Zone] = relationship(lazy="joined")


class Ward(Base):
    __tablename__ = "bvms_ward"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[int] = mapped_column(Integer, unique=True)
    name_en: Mapped[str] = mapped_column(String(120), default="")
    name_hi: Mapped[str] = mapped_column(String(120), default="")
    zone_id: Mapped[int] = mapped_column(ForeignKey("bvms_zone.id"))
    division_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_division.id", ondelete="SET NULL"), nullable=True)
    boundary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    zone: Mapped[Zone] = relationship(lazy="joined")
    division: Mapped[Optional[Division]] = relationship(lazy="joined")


class Branch(Base):
    __tablename__ = "bvms_branch"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(120))
    name_hi: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    head_designation: Mapped[str] = mapped_column(String(120), default="")
    default_response_days: Mapped[int] = mapped_column(Integer, default=7)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    officers: Mapped[list["OfficerProfile"]] = relationship(back_populates="branch")


officer_zones = Table("bvms_officer_profile_zones", Base.metadata,
                      Column("id", Integer, primary_key=True, autoincrement=True),
                      Column("officerprofile_id", ForeignKey("bvms_officer_profile.id", ondelete="CASCADE"), nullable=False),
                      Column("zone_id", ForeignKey("bvms_zone.id", ondelete="CASCADE"), nullable=False),
                      UniqueConstraint("officerprofile_id", "zone_id"))
officer_wards = Table("bvms_officer_profile_wards", Base.metadata,
                      Column("id", Integer, primary_key=True, autoincrement=True),
                      Column("officerprofile_id", ForeignKey("bvms_officer_profile.id", ondelete="CASCADE"), nullable=False),
                      Column("ward_id", ForeignKey("bvms_ward.id", ondelete="CASCADE"), nullable=False),
                      UniqueConstraint("officerprofile_id", "ward_id"))
officer_divisions = Table("bvms_officer_profile_divisions", Base.metadata,
                          Column("id", Integer, primary_key=True, autoincrement=True),
                          Column("officerprofile_id", ForeignKey("bvms_officer_profile.id", ondelete="CASCADE"), nullable=False),
                          Column("division_id", ForeignKey("bvms_division.id", ondelete="CASCADE"), nullable=False),
                          UniqueConstraint("officerprofile_id", "division_id"))


class OfficerProfile(Base):
    """Role and jurisdiction of a platform user inside this module."""
    __tablename__ = "bvms_officer_profile"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    role: Mapped[str] = mapped_column(String(24))
    designation: Mapped[str] = mapped_column(String(120), default="")
    employee_code: Mapped[str] = mapped_column(String(40), default="")
    mobile: Mapped[str] = mapped_column(String(15), index=True)
    email: Mapped[str] = mapped_column(String(254), default="")
    reports_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_officer_profile.id", ondelete="SET NULL"), nullable=True)
    delegation_order_no: Mapped[str] = mapped_column(String(120), default="")
    delegation_order_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    signature_image: Mapped[str] = mapped_column(String(300), default="")
    parent_profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_officer_profile.id", ondelete="CASCADE"), nullable=True)
    branch_id: Mapped[Optional[str]] = mapped_column(ForeignKey("bvms_branch.code", ondelete="SET NULL"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="bvms_profile", foreign_keys=[user_id], lazy="joined")
    zones: Mapped[list[Zone]] = relationship(secondary=officer_zones, lazy="selectin")
    wards: Mapped[list[Ward]] = relationship(secondary=officer_wards, lazy="selectin")
    divisions: Mapped[list[Division]] = relationship(secondary=officer_divisions, lazy="selectin")
    reports_to: Mapped[Optional["OfficerProfile"]] = relationship(remote_side=[id], foreign_keys=[reports_to_id], post_update=True)
    parent_profile: Mapped[Optional["OfficerProfile"]] = relationship(remote_side=[id], foreign_keys=[parent_profile_id], post_update=True)
    branch: Mapped[Optional[Branch]] = relationship(back_populates="officers", lazy="joined")
    permission_overrides: Mapped[list["OfficerPermissionOverride"]] = relationship(back_populates="profile", cascade="all, delete-orphan", lazy="selectin")

    @property
    def display_name(self) -> str:
        u = self.user
        full = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        return full or getattr(u, "username", "") or str(u)

    def get_role_display(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)


class LegalStatute(Base):
    __tablename__ = "bvms_legal_statute"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    citation: Mapped[str] = mapped_column(String(300), default="")
    jurisdiction: Mapped[str] = mapped_column(String(200), default="")
    primary: Mapped[bool] = mapped_column(Boolean, default=True)
    sections: Mapped[list["LegalSection"]] = relationship(back_populates="statute")


class LegalSection(Base):
    __tablename__ = "bvms_legal_section"
    __table_args__ = (UniqueConstraint("statute_id", "section"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    statute_id: Mapped[str] = mapped_column(ForeignKey("bvms_legal_statute.code", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(String(30))
    heading: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20), default="substantive")
    text: Mapped[str] = mapped_column(Text)
    schedule_fine_inr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    schedule_daily_fine_inr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    verify: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    statute: Mapped[LegalStatute] = relationship(back_populates="sections", lazy="joined")


class ViolationType(Base):
    __tablename__ = "bvms_violation_type"
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    category: Mapped[str] = mapped_column(String(40))
    title_en: Mapped[str] = mapped_column(String(250))
    title_hi: Mapped[str] = mapped_column(String(250), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    contravention_of: Mapped[str] = mapped_column(Text, default="")
    legal_basis: Mapped[list] = mapped_column(JSON, default=list)
    action_path: Mapped[str] = mapped_column(String(30))
    orders_available: Mapped[list] = mapped_column(JSON, default=list)
    scn_response_days_default: Mapped[int] = mapped_column(Integer, default=7)
    order_compliance_days_default: Mapped[int] = mapped_column(Integer, default=15)
    statutory_minimum_days: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[str] = mapped_column(String(10), default="HIGH")
    compoundable: Mapped[str] = mapped_column(String(12), default="NO")
    evidence_checklist: Mapped[list] = mapped_column(JSON, default=list)
    schedule_fine_inr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    schedule_daily_fine_inr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    appeal: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class OrderType(Base):
    __tablename__ = "bvms_order_type"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    title_en: Mapped[str] = mapped_column(String(250))
    title_hi: Mapped[str] = mapped_column(String(250), default="")
    statute: Mapped[str] = mapped_column(String(20))
    section: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(12))
    min_days: Mapped[int] = mapped_column(Integer, default=0)
    default_days: Mapped[int] = mapped_column(Integer, default=0)
    template: Mapped[str] = mapped_column(String(80))
    appeal_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    appeal_to: Mapped[str] = mapped_column(String(200), default="")
    body_override_en: Mapped[str] = mapped_column(Text, default="")
    body_override_hi: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SLAConfig(Base):
    __tablename__ = "bvms_sla_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stage: Mapped[str] = mapped_column(String(40), unique=True)
    label: Mapped[str] = mapped_column(String(120))
    hours: Mapped[int] = mapped_column(Integer, default=72)
    escalate_to_role: Mapped[str] = mapped_column(String(24), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# ============================================================================
# 2. GIS: government land parcels
# ============================================================================
class LandLayerUpload(Base):
    __tablename__ = "bvms_land_layer_upload"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    name: Mapped[str] = mapped_column(String(200))
    layer_key: Mapped[str] = mapped_column(String(80), index=True, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    replaces_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_land_layer_upload.id", ondelete="SET NULL"), nullable=True)
    agency: Mapped[str] = mapped_column(String(20))
    source_file: Mapped[str] = mapped_column(String(300), default="")
    file_format: Mapped[str] = mapped_column(String(10), default="GEOJSON")
    source: Mapped[str] = mapped_column(String(200), default="")
    survey_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    feature_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    import_log: Mapped[str] = mapped_column(Text, default="")
    uploaded_by: Mapped[Optional[User]] = relationship(lazy="joined")
    parcels: Mapped[list["GovtLandParcel"]] = relationship(back_populates="layer_upload")


class GovtLandParcel(Base):
    __tablename__ = "bvms_govt_land_parcel"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    name: Mapped[str] = mapped_column(String(200), default="")
    agency: Mapped[str] = mapped_column(String(20), default="MCG")
    land_use: Mapped[str] = mapped_column(String(120), default="")
    village: Mapped[str] = mapped_column(String(120), default="")
    khasra_no: Mapped[str] = mapped_column(String(120), default="")
    area_sqm: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_ward.id", ondelete="SET NULL"), nullable=True)
    geometry: Mapped[dict] = mapped_column(JSON)
    bbox: Mapped[list] = mapped_column(JSON, default=list)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    layer_upload_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_land_layer_upload.id", ondelete="SET NULL"), nullable=True)
    layer_key: Mapped[str] = mapped_column(String(80), default="", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    ward: Mapped[Optional[Ward]] = relationship()
    layer_upload: Mapped[Optional[LandLayerUpload]] = relationship(back_populates="parcels")

    def get_agency_display(self):
        return AGENCY_LABELS.get(self.agency, self.agency)


# ============================================================================
# 3. Sanctioned building plans / licences register
# ============================================================================
class SanctionedPlan(Base):
    __tablename__ = "bvms_sanctioned_plan"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    plan_no: Mapped[str] = mapped_column(String(80), unique=True)
    pid: Mapped[str] = mapped_column(String(40), default="", index=True)
    address: Mapped[str] = mapped_column(Text)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_ward.id", ondelete="SET NULL"), nullable=True)
    zone_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_zone.id", ondelete="SET NULL"), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    owner_name: Mapped[str] = mapped_column(String(200))
    owner_mobile: Mapped[str] = mapped_column(String(15), default="")
    plot_area_sqm: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    land_use: Mapped[str] = mapped_column(String(60), default="")
    building_type: Mapped[str] = mapped_column(String(80), default="")
    sanctioned_on: Mapped[date] = mapped_column(Date)
    valid_till: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sanction_mode: Mapped[str] = mapped_column(String(40), default="")
    permitted_floors: Mapped[str] = mapped_column(String(40), default="")
    permitted_ground_coverage_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    permitted_far: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    permitted_height_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    setbacks: Mapped[dict] = mapped_column(JSON, default=dict)
    licence_no: Mapped[str] = mapped_column(String(80), default="")
    licence_holder: Mapped[str] = mapped_column(String(200), default="")
    licence_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    licence_valid_till: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    licence_authority: Mapped[str] = mapped_column(String(120), default="")
    colony_name: Mapped[str] = mapped_column(String(160), default="")
    architect_name: Mapped[str] = mapped_column(String(160), default="")
    architect_registration_no: Mapped[str] = mapped_column(String(80), default="")
    dpc_certificate_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    occupation_certificate_no: Mapped[str] = mapped_column(String(80), default="")
    occupation_certificate_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="VALID")
    source: Mapped[str] = mapped_column(String(20), default="MANUAL")
    external_ref: Mapped[str] = mapped_column(String(120), default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ward: Mapped[Optional[Ward]] = relationship(lazy="joined")
    zone: Mapped[Optional[Zone]] = relationship(lazy="joined")
    documents: Mapped[list["MediaAttachment"]] = relationship(back_populates="sanctioned_plan", foreign_keys="MediaAttachment.sanctioned_plan_id")
    cases: Mapped[list["ViolationCase"]] = relationship(back_populates="sanctioned_plan", foreign_keys="ViolationCase.sanctioned_plan_id")


# ============================================================================
# 4. Media (geotagged photos / videos / documents)
# ============================================================================
class MediaAttachment(UuidPK, Base):
    __tablename__ = "bvms_media"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_case.id", ondelete="CASCADE"), nullable=True, index=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_inspection_task.id", ondelete="SET NULL"), nullable=True)
    notice_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_notice.id", ondelete="SET NULL"), nullable=True)
    sanctioned_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_sanctioned_plan.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="INSPECTION")
    media_type: Mapped[str] = mapped_column(String(10), default="IMAGE")
    file: Mapped[str] = mapped_column(String(300))                       # storage key (S3) / path under UPLOADS_DIR
    original_name: Mapped[str] = mapped_column(String(255), default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    accuracy_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    altitude_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    captured_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    device_id: Mapped[str] = mapped_column(String(120), default="")
    distance_from_case_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    geotag_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    integrity_status: Mapped[str] = mapped_column(String(12), default="UNVERIFIED", index=True)
    integrity_check_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_location_integrity.id", ondelete="SET NULL"), nullable=True)
    caption: Mapped[str] = mapped_column(String(300), default="")
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    case: Mapped[Optional["ViolationCase"]] = relationship(back_populates="media", foreign_keys=[case_id])
    task: Mapped[Optional["InspectionTask"]] = relationship(back_populates="media", foreign_keys=[task_id])
    notice: Mapped[Optional["Notice"]] = relationship(back_populates="media", foreign_keys=[notice_id])
    sanctioned_plan: Mapped[Optional[SanctionedPlan]] = relationship(back_populates="documents", foreign_keys=[sanctioned_plan_id])
    uploaded_by: Mapped[Optional[User]] = relationship(lazy="joined")
    integrity_check: Mapped[Optional["LocationIntegrityCheck"]] = relationship(foreign_keys=[integrity_check_id])


# ============================================================================
# 5. The case
# ============================================================================
class Sequence(Base):
    """Atomic counters for case / notice numbering."""
    __tablename__ = "bvms_sequence"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


class ViolationCase(UuidPK, Base):
    __tablename__ = "bvms_case"
    __table_args__ = (Index("ix_bvms_case_status_zone", "status", "zone_id"), Index("ix_bvms_case_ward_status", "ward_id", "status"),
                      Index("ix_bvms_case_land_type", "land_type"), Index("ix_bvms_case_compliance_due", "compliance_due_at"), Index("ix_bvms_case_response_due", "response_due_at"))
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    case_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    status_changed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    source: Mapped[str] = mapped_column(String(20), default="FIELD_INSPECTION")
    legacy_reference: Mapped[str] = mapped_column(String(120), default="")
    legacy_batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_legacy_batch.id", ondelete="SET NULL"), nullable=True)
    complaint_ref: Mapped[str] = mapped_column(String(80), default="")
    priority: Mapped[str] = mapped_column(String(10), default="NORMAL")
    # property
    pid: Mapped[str] = mapped_column(String(40), default="", index=True)
    pid_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    pid_linked_mobile: Mapped[str] = mapped_column(String(15), default="")
    alternate_mobile: Mapped[str] = mapped_column(String(15), default="")
    address_line: Mapped[str] = mapped_column(Text, default="")
    locality: Mapped[str] = mapped_column(String(160), default="")
    sector: Mapped[str] = mapped_column(String(60), default="")
    village_colony: Mapped[str] = mapped_column(String(160), default="")
    pincode: Mapped[str] = mapped_column(String(6), default="")
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_ward.id", ondelete="SET NULL"), nullable=True)
    zone_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_zone.id", ondelete="SET NULL"), nullable=True)
    division_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_division.id", ondelete="SET NULL"), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    location_accuracy_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    land_type: Mapped[str] = mapped_column(String(12), default="UNKNOWN")
    govt_parcel_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_govt_land_parcel.id", ondelete="SET NULL"), nullable=True)
    sanctioned_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_sanctioned_plan.id", ondelete="SET NULL"), nullable=True)
    # persons
    owner_name: Mapped[str] = mapped_column(String(200), default="")
    owner_father_name: Mapped[str] = mapped_column(String(200), default="")
    occupier_name: Mapped[str] = mapped_column(String(200), default="")
    builder_name: Mapped[str] = mapped_column(String(200), default="")
    person_on_site: Mapped[str] = mapped_column(String(200), default="")
    # construction
    construction_stage: Mapped[str] = mapped_column(String(20), default="UNDER_CONSTRUCTION")
    plot_area_sqm: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    covered_area_sqm: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    storeys: Mapped[str] = mapped_column(String(40), default="")
    height_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    use_observed: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    measurements: Mapped[dict] = mapped_column(JSON, default=dict)
    # workflow ownership
    reported_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assigned_ae_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_jc_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    current_owner_role: Mapped[str] = mapped_column(String(24), default="JE")
    stage_due_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    # key dates
    inspected_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    ae_forwarded_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    jc_received_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    scn_issued_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    scn_served_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    response_due_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    response_received_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    hearing_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    order_issued_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    order_served_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    compliance_due_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    # planned inspection
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_inspection_task.id", ondelete="SET NULL"), nullable=True, unique=True)
    inspector_latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    inspector_longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    inspector_distance_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    # litigation flag
    litigation_status: Mapped[str] = mapped_column(String(20), default="NONE", index=True)
    litigation_authority: Mapped[str] = mapped_column(String(30), default="")
    stay_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_hearing_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # outcome
    stop_work_issued: Mapped[bool] = mapped_column(Boolean, default=False)
    sealed: Mapped[bool] = mapped_column(Boolean, default=False)
    decision: Mapped[str] = mapped_column(String(30), default="")
    decision_reasons: Mapped[str] = mapped_column(Text, default="")
    final_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_notice.id", ondelete="SET NULL", use_alter=True, name="fk_case_final_order"), nullable=True)
    closure_reason: Mapped[str] = mapped_column(Text, default="")
    demolition_cost_inr: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    cost_recovery_status: Mapped[str] = mapped_column(String(20), default="")

    ward: Mapped[Optional[Ward]] = relationship(lazy="joined")
    zone: Mapped[Optional[Zone]] = relationship(lazy="joined")
    division: Mapped[Optional[Division]] = relationship()
    govt_parcel: Mapped[Optional[GovtLandParcel]] = relationship()
    sanctioned_plan: Mapped[Optional[SanctionedPlan]] = relationship(back_populates="cases", foreign_keys=[sanctioned_plan_id])
    reported_by: Mapped[User] = relationship(foreign_keys=[reported_by_id], lazy="joined")
    assigned_ae: Mapped[Optional[User]] = relationship(foreign_keys=[assigned_ae_id], lazy="joined")
    assigned_jc: Mapped[Optional[User]] = relationship(foreign_keys=[assigned_jc_id], lazy="joined")
    final_order: Mapped[Optional["Notice"]] = relationship(foreign_keys=[final_order_id], post_update=True)
    task: Mapped[Optional["InspectionTask"]] = relationship(back_populates="case", foreign_keys=[task_id], post_update=True)
    legacy_batch: Mapped[Optional["LegacyOrderBatch"]] = relationship(back_populates="cases")
    violations: Mapped[list["CaseViolation"]] = relationship(back_populates="case", cascade="all, delete-orphan", order_by="CaseViolation.id")
    media: Mapped[list[MediaAttachment]] = relationship(back_populates="case", foreign_keys=[MediaAttachment.case_id], order_by="desc(MediaAttachment.created_at)")
    notices: Mapped[list["Notice"]] = relationship(back_populates="case", foreign_keys="Notice.case_id", order_by="desc(Notice.issued_at)")
    responses: Mapped[list["CaseResponse"]] = relationship(back_populates="case", order_by="desc(CaseResponse.received_on)")
    hearings: Mapped[list["Hearing"]] = relationship(back_populates="case", order_by="desc(Hearing.scheduled_at)")
    appeals: Mapped[list["Appeal"]] = relationship(back_populates="case", order_by="desc(Appeal.filed_on), desc(Appeal.id)")
    executions: Mapped[list["ExecutionRecord"]] = relationship(back_populates="case", order_by="desc(ExecutionRecord.executed_on)")
    events: Mapped[list["CaseEvent"]] = relationship(back_populates="case", order_by="CaseEvent.at, CaseEvent.id")
    referrals: Mapped[list["BranchReferral"]] = relationship(back_populates="case", order_by="desc(BranchReferral.referred_at)")
    integrity_checks: Mapped[list["LocationIntegrityCheck"]] = relationship(back_populates="case", foreign_keys="LocationIntegrityCheck.case_id")

    def get_status_display(self):
        return STATUS_LABELS.get(self.status, self.status)

    def get_land_type_display(self):
        return LAND_TYPE_LABELS.get(self.land_type, self.land_type)

    def get_construction_stage_display(self):
        return CONSTRUCTION_STAGE_LABELS.get(self.construction_stage, self.construction_stage)

    def __str__(self):
        return self.case_no


class CaseViolation(Base):
    __tablename__ = "bvms_case_violation"
    __table_args__ = (UniqueConstraint("case_id", "violation_type_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bvms_case.id", ondelete="CASCADE"))
    violation_type_id: Mapped[str] = mapped_column(ForeignKey("bvms_violation_type.code", ondelete="RESTRICT"))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    remarks: Mapped[str] = mapped_column(Text, default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    case: Mapped[ViolationCase] = relationship(back_populates="violations")
    violation_type: Mapped[ViolationType] = relationship(lazy="joined")


class Notice(UuidPK, Base):
    """A show-cause notice, order, memo or referral generated for a case."""
    __tablename__ = "bvms_notice"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bvms_case.id", ondelete="CASCADE"), index=True)
    order_type_id: Mapped[str] = mapped_column(ForeignKey("bvms_order_type.code", ondelete="RESTRICT"))
    notice_no: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(12))
    issued_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    addressee_name: Mapped[str] = mapped_column(String(200), default="")
    addressee_address: Mapped[str] = mapped_column(Text, default="")
    addressee_mobiles: Mapped[list] = mapped_column(JSON, default=list)
    response_days: Mapped[int] = mapped_column(Integer, default=0)
    response_due_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    compliance_days: Mapped[int] = mapped_column(Integer, default=0)
    compliance_due_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    hearing_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    hearing_venue: Mapped[str] = mapped_column(String(200), default="")
    operative_text_en: Mapped[str] = mapped_column(Text, default="")
    operative_text_hi: Mapped[str] = mapped_column(Text, default="")
    html_snapshot: Mapped[str] = mapped_column(Text, default="")
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    pdf: Mapped[str] = mapped_column(String(300), default="")
    signed_pdf: Mapped[str] = mapped_column(String(300), default="")
    document_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    verification_code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    qr_payload: Mapped[str] = mapped_column(Text, default="")
    signature_status: Mapped[str] = mapped_column(String(10), default="UNSIGNED")
    signer_name: Mapped[str] = mapped_column(String(200), default="")
    signer_cert_subject: Mapped[str] = mapped_column(String(300), default="")
    signer_cert_serial: Mapped[str] = mapped_column(String(120), default="")
    signed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    signature_error: Mapped[str] = mapped_column(Text, default="")
    served_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    served_mode: Mapped[str] = mapped_column(String(16), default="")
    served_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    service_remarks: Mapped[str] = mapped_column(Text, default="")
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_notice.id", ondelete="SET NULL"), nullable=True)
    is_final_order: Mapped[bool] = mapped_column(Boolean, default=False)
    is_legacy: Mapped[bool] = mapped_column(Boolean, default=False)

    case: Mapped[ViolationCase] = relationship(back_populates="notices", foreign_keys=[case_id])
    order_type: Mapped[OrderType] = relationship(lazy="joined")
    issued_by: Mapped[User] = relationship(foreign_keys=[issued_by_id], lazy="joined")
    served_by: Mapped[Optional[User]] = relationship(foreign_keys=[served_by_id], lazy="joined")
    dispatches: Mapped[list["NoticeDispatch"]] = relationship(back_populates="notice", cascade="all, delete-orphan", order_by="NoticeDispatch.id")
    media: Mapped[list[MediaAttachment]] = relationship(back_populates="notice", foreign_keys=[MediaAttachment.notice_id])
    responses: Mapped[list["CaseResponse"]] = relationship(back_populates="notice")

    def __str__(self):
        return self.notice_no


class NoticeDispatch(Base):
    __tablename__ = "bvms_notice_dispatch"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    notice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bvms_notice.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(10), default="SMS")
    to: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="QUEUED")
    provider_ref: Mapped[str] = mapped_column(String(120), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    notice: Mapped[Notice] = relationship(back_populates="dispatches")


class CaseResponse(Base):
    """Reply of the noticee to a show-cause notice."""
    __tablename__ = "bvms_case_response"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bvms_case.id", ondelete="CASCADE"))
    notice_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_notice.id", ondelete="SET NULL"), nullable=True)
    received_on: Mapped[date] = mapped_column(Date)
    received_via: Mapped[str] = mapped_column(String(10))
    submitted_by_name: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text)
    requests_hearing: Mapped[bool] = mapped_column(Boolean, default=False)
    is_within_time: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    ae_comments: Mapped[str] = mapped_column(Text, default="")
    ae_commented_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    jc_remarks: Mapped[str] = mapped_column(Text, default="")
    case: Mapped[ViolationCase] = relationship(back_populates="responses")
    notice: Mapped[Optional[Notice]] = relationship(back_populates="responses")
    uploaded_by: Mapped[User] = relationship(lazy="joined")


class Hearing(Base):
    __tablename__ = "bvms_hearing"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bvms_case.id", ondelete="CASCADE"))
    notice_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_notice.id", ondelete="SET NULL"), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime)
    venue: Mapped[str] = mapped_column(String(200), default="")
    presiding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    held_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    attendees: Mapped[str] = mapped_column(Text, default="")
    proceedings: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(String(30), default="")
    next_date: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    case: Mapped[ViolationCase] = relationship(back_populates="hearings")
    notice: Mapped[Optional[Notice]] = relationship()
    presiding: Mapped[User] = relationship(lazy="joined")


class Appeal(Base):
    """An appeal / writ / suit against a notice or order, and the stay (if any) granted in it."""
    __tablename__ = "bvms_appeal"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bvms_case.id", ondelete="CASCADE"))
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_notice.id", ondelete="SET NULL"), nullable=True)
    authority: Mapped[str] = mapped_column(String(30))
    authority_other: Mapped[str] = mapped_column(String(200), default="")
    filed_on: Mapped[date] = mapped_column(Date)
    appeal_no: Mapped[str] = mapped_column(String(120), default="")
    appellant_name: Mapped[str] = mapped_column(String(200), default="")
    counsel_for_mcg: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    stay_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    stay_order_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    stay_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    stay_scope: Mapped[str] = mapped_column(String(20), default="")
    stay_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_media.id", ondelete="SET NULL"), nullable=True)
    conditions: Mapped[str] = mapped_column(Text, default="")
    next_hearing_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    decided_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    decision_summary: Mapped[str] = mapped_column(Text, default="")
    final_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_media.id", ondelete="SET NULL"), nullable=True)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    case: Mapped[ViolationCase] = relationship(back_populates="appeals")
    order: Mapped[Optional[Notice]] = relationship(foreign_keys=[order_id])
    stay_order: Mapped[Optional[MediaAttachment]] = relationship(foreign_keys=[stay_order_id])
    final_order: Mapped[Optional[MediaAttachment]] = relationship(foreign_keys=[final_order_id])
    recorded_by: Mapped[User] = relationship(lazy="joined")

    def get_authority_display(self):
        return AUTHORITY_LABELS.get(self.authority, self.authority)

    def get_status_display(self):
        return APPEAL_STATUS_LABELS.get(self.status, self.status)

    @property
    def is_stay_active(self) -> bool:
        from app.core.timeutil import localdate
        return self.status == AppealStatus.STAYED and (self.stay_until is None or self.stay_until >= localdate())


class ExecutionRecord(Base):
    __tablename__ = "bvms_execution"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bvms_case.id", ondelete="CASCADE"))
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_notice.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(12))
    executed_on: Mapped[datetime] = mapped_column(UTCDateTime)
    squad_incharge: Mapped[str] = mapped_column(String(200), default="")
    police_assistance: Mapped[bool] = mapped_column(Boolean, default=False)
    police_station: Mapped[str] = mapped_column(String(120), default="")
    duty_magistrate: Mapped[str] = mapped_column(String(200), default="")
    machinery_used: Mapped[str] = mapped_column(String(300), default="")
    area_demolished_sqm: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    seal_memo_no: Mapped[str] = mapped_column(String(60), default="")
    cost_incurred_inr: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    verified_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    case: Mapped[ViolationCase] = relationship(back_populates="executions")
    order: Mapped[Optional[Notice]] = relationship()
    recorded_by: Mapped[User] = relationship(foreign_keys=[recorded_by_id], lazy="joined")
    verified_by: Mapped[Optional[User]] = relationship(foreign_keys=[verified_by_id], lazy="joined")


# ============================================================================
# 6. Audit trail (hash-chained) and notifications
# ============================================================================
class CaseEvent(Base):
    __tablename__ = "bvms_case_event"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bvms_case.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(24), default="")
    action: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str] = mapped_column(String(30), default="")
    to_status: Mapped[str] = mapped_column(String(30), default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    device_id: Mapped[str] = mapped_column(String(120), default="")
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    case: Mapped[ViolationCase] = relationship(back_populates="events")
    actor: Mapped[Optional[User]] = relationship(lazy="joined")

    def compute_hash(self) -> str:
        body = json.dumps({"case": str(self.case_id), "at": self.at.isoformat(), "actor": self.actor_id, "action": self.action, "from": self.from_status,
                           "to": self.to_status, "remarks": self.remarks, "payload": self.payload, "prev": self.prev_hash}, sort_keys=True, default=str)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


class Notification(Base):
    __tablename__ = "bvms_notification"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_case.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(10), default="INFO")
    read_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    case: Mapped[Optional[ViolationCase]] = relationship()


class OTPRequest(Base):
    __tablename__ = "bvms_otp"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mobile: Mapped[str] = mapped_column(String(15), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


# ============================================================================
# 7. Branch referrals
# ============================================================================
class BranchReferral(Base):
    __tablename__ = "bvms_branch_referral"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bvms_case.id", ondelete="CASCADE"))
    branch_id: Mapped[str] = mapped_column(ForeignKey("bvms_branch.code", ondelete="RESTRICT"))
    referred_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    referred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    query: Mapped[str] = mapped_column(Text)
    due_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    hold_case: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(12), default="PENDING", index=True)
    assigned_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    response: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(String(40), default="")
    responded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    closed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    closing_remarks: Mapped[str] = mapped_column(Text, default="")
    case: Mapped[ViolationCase] = relationship(back_populates="referrals")
    branch: Mapped[Branch] = relationship(lazy="joined")
    referred_by: Mapped[User] = relationship(foreign_keys=[referred_by_id], lazy="joined")
    assigned_to: Mapped[Optional[User]] = relationship(foreign_keys=[assigned_to_id], lazy="joined")
    responded_by: Mapped[Optional[User]] = relationship(foreign_keys=[responded_by_id], lazy="joined")
    closed_by: Mapped[Optional[User]] = relationship(foreign_keys=[closed_by_id], lazy="joined")


# ============================================================================
# 8. Admin-configurable workflow, permissions and audit of admin changes
# ============================================================================
class WorkflowRule(Base):
    __tablename__ = "bvms_workflow_rule"
    __table_args__ = (UniqueConstraint("status", "role", "action"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(30))
    role: Mapped[str] = mapped_column(String(24))
    action: Mapped[str] = mapped_column(String(40))
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)


class WorkflowSetting(Base):
    __tablename__ = "bvms_workflow_setting"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[object] = mapped_column(JSON)
    value_type: Mapped[str] = mapped_column(String(10), default="bool")
    label: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    group: Mapped[str] = mapped_column(String(40), default="Routing")
    choices: Mapped[list] = mapped_column(JSON, default=list)
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)


class RolePermission(Base):
    __tablename__ = "bvms_role_permission"
    __table_args__ = (UniqueConstraint("role", "permission"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(24))
    permission: Mapped[str] = mapped_column(String(40))
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)


class OfficerPermissionOverride(Base):
    __tablename__ = "bvms_officer_permission_override"
    __table_args__ = (UniqueConstraint("profile_id", "permission"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("bvms_officer_profile.id", ondelete="CASCADE"))
    permission: Mapped[str] = mapped_column(String(40))
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str] = mapped_column(String(300), default="")
    order_reference: Mapped[str] = mapped_column(String(120), default="")
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    profile: Mapped[OfficerProfile] = relationship(back_populates="permission_overrides")


class AdminAuditLog(Base):
    __tablename__ = "bvms_admin_audit_log"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    target_type: Mapped[str] = mapped_column(String(40), default="")
    target_id: Mapped[str] = mapped_column(String(60), default="")
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    order_reference: Mapped[str] = mapped_column(String(120), default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    actor: Mapped[Optional[User]] = relationship(lazy="joined")


# ============================================================================
# 9. Planned inspections
# ============================================================================
class InspectionBatch(Base):
    __tablename__ = "bvms_inspection_batch"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), default="VERIFICATION")
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    source_file: Mapped[str] = mapped_column(String(300), default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[User] = relationship(lazy="joined")
    tasks: Mapped[list["InspectionTask"]] = relationship(back_populates="batch")


class InspectionTask(Base):
    __tablename__ = "bvms_inspection_task"
    __table_args__ = (Index("ix_bvms_task_assigned_status", "assigned_to_id", "status"), Index("ix_bvms_task_status_zone", "status", "zone_id"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_inspection_batch.id", ondelete="SET NULL"), nullable=True)
    category: Mapped[str] = mapped_column(String(24), default="VERIFICATION")
    pid: Mapped[str] = mapped_column(String(40), default="", index=True)
    pid_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    address: Mapped[str] = mapped_column(Text, default="")
    owner_name: Mapped[str] = mapped_column(String(200), default="")
    owner_mobile: Mapped[str] = mapped_column(String(15), default="")
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_ward.id", ondelete="SET NULL"), nullable=True)
    zone_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_zone.id", ondelete="SET NULL"), nullable=True)
    instructions: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(10), default="NORMAL")
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assigned_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="UNASSIGNED", index=True)
    related_case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_case.id", ondelete="SET NULL", use_alter=True, name="fk_task_related_case"), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    start_latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    start_longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    start_distance_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    outcome_remarks: Mapped[str] = mapped_column(Text, default="")
    geofence_m: Mapped[int] = mapped_column(Integer, default=100)
    batch: Mapped[Optional[InspectionBatch]] = relationship(back_populates="tasks", lazy="joined")
    ward: Mapped[Optional[Ward]] = relationship(lazy="joined")
    zone: Mapped[Optional[Zone]] = relationship(lazy="joined")
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id], lazy="joined")
    assigned_to: Mapped[Optional[User]] = relationship(foreign_keys=[assigned_to_id], lazy="joined")
    related_case: Mapped[Optional[ViolationCase]] = relationship(foreign_keys=[related_case_id], post_update=True)
    case: Mapped[Optional[ViolationCase]] = relationship(back_populates="task", foreign_keys=[ViolationCase.task_id], uselist=False, post_update=True)
    media: Mapped[list[MediaAttachment]] = relationship(back_populates="task", foreign_keys=[MediaAttachment.task_id])
    integrity_checks: Mapped[list["LocationIntegrityCheck"]] = relationship(back_populates="task", foreign_keys="LocationIntegrityCheck.task_id")

    def get_status_display(self):
        return TASK_STATUS_LABELS.get(self.status, self.status)

    def get_category_display(self):
        return TASK_CATEGORY_LABELS.get(self.category, self.category)


# ============================================================================
# 13. Location integrity (anti-GPS-spoofing)
# ============================================================================
class LocationIntegrityCheck(Base):
    __tablename__ = "bvms_location_integrity"
    __table_args__ = (Index("ix_bvms_li_officer_at", "officer_id", "at"), Index("ix_bvms_li_decision_at", "decision", "at"))
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    officer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    context: Mapped[str] = mapped_column(String(14))
    decision: Mapped[str] = mapped_column(String(10), index=True, default="PASS")
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_case.id", ondelete="SET NULL"), nullable=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_inspection_task.id", ondelete="SET NULL"), nullable=True)
    media_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bvms_media.id", ondelete="SET NULL", use_alter=True, name="fk_li_media"), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    accuracy_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    altitude_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    speed_mps: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    heading: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    provider: Mapped[str] = mapped_column(String(30), default="")
    fix_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True, index=True)
    fix_age_s: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    jitter_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    device_id: Mapped[str] = mapped_column(String(120), default="")
    platform: Mapped[str] = mapped_column(String(10), default="")
    source: Mapped[str] = mapped_column(String(10), default="")
    app_version: Mapped[str] = mapped_column(String(40), default="")
    build_number: Mapped[str] = mapped_column(String(40), default="")
    os_version: Mapped[str] = mapped_column(String(40), default="")
    device_model: Mapped[str] = mapped_column(String(80), default="")
    native_module: Mapped[bool] = mapped_column(Boolean, default=False)
    is_physical_device: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    mock_location: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    rooted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    developer_options: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    vpn_active: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    proxy_configured: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    simulated_by_software: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    produced_by_accessory: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    attestation_type: Mapped[str] = mapped_column(String(20), default="")
    attestation_status: Mapped[str] = mapped_column(String(12), default="NONE")
    attestation_detail: Mapped[dict] = mapped_column(JSON, default=dict)
    client_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    ip_intel: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_distance_km: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 1), nullable=True)
    previous_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bvms_location_integrity.id", ondelete="SET NULL"), nullable=True)
    travel_distance_km: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    travel_speed_kmph: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 1), nullable=True)
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    officer: Mapped[Optional[User]] = relationship(lazy="joined")
    case: Mapped[Optional[ViolationCase]] = relationship(back_populates="integrity_checks", foreign_keys=[case_id])
    task: Mapped[Optional[InspectionTask]] = relationship(back_populates="integrity_checks", foreign_keys=[task_id])
    previous: Mapped[Optional["LocationIntegrityCheck"]] = relationship(remote_side=[id], foreign_keys=[previous_id])

    def get_context_display(self):
        return INTEGRITY_CONTEXT_LABELS.get(self.context, self.context)


class IntegrityNonce(Base):
    __tablename__ = "bvms_integrity_nonce"
    nonce: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    used_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)


class AppAttestKey(Base):
    __tablename__ = "bvms_app_attest_key"
    key_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    public_key_pem: Mapped[str] = mapped_column(Text)
    counter: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0)
    environment: Mapped[str] = mapped_column(String(12), default="production")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)


# ============================================================================
# 14. Orders issued before the system (legacy register imports)
# ============================================================================
class LegacyOrderBatch(Base):
    __tablename__ = "bvms_legacy_batch"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    source_file: Mapped[str] = mapped_column(String(300), default="")
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[Optional[User]] = relationship(lazy="joined")
    cases: Mapped[list[ViolationCase]] = relationship(back_populates="legacy_batch")


# ---------------------------------------------------------------------------------------------
# Choice classes reachable from their models, as in the Django edition (InspectionTask.Status ...)
# ---------------------------------------------------------------------------------------------
InspectionTask.Status = TaskStatus
InspectionTask.Category = TaskCategory
Appeal.Status = AppealStatus
Appeal.Authority = AppealAuthority
Appeal.StayScope = StayScope
ExecutionRecord.Mode = ExecutionMode
ExecutionRecord.Action = ExecutionAction
Notice.SignatureStatus = SignatureStatus
Notice.ServiceMode = ServiceMode
CaseResponse.ReceivedVia = ReceivedVia
BranchReferral.Status = ReferralStatus
LocationIntegrityCheck.Context = IntegrityContext
