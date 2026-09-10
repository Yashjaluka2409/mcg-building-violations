"""
The case workflow (state machine). Every transition:
  1. validates the actor's role and the current status,
  2. mutates the case, 3. writes a hash-chained CaseEvent, 4. computes the SLA due time,
  5. notifies the next owner.

Legal timelines implemented here (see shared/legal):
  * SCN u/s 261 proviso: reasonable opportunity (default 7 days, configurable per violation type)
  * SCN u/s 408A(1): 7 days (statutory)          * order u/s 408A(2): further 7 days (statutory)
  * demolition order u/s 261(1): >= 3 days (statutory minimum); MCG default 15 days (as decided)
  * sealing u/s 263A: appeal 7 days to Divisional Commissioner
  * HPPA s.4: notice >= 10 days ; s.5(2): 30 days before force
  * s.284: >= 30 days to vacate + 6 weeks to demolish
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..models import (
    Appeal, Branch, BranchReferral, CaseResponse, CaseStatus, CaseViolation, ExecutionRecord, Hearing, LandType, MediaAttachment, Notice,
    OfficerProfile, OrderType, Role, ViolationCase, ViolationType,
)
from . import access
from .audit import record_event
from .geo import haversine_m, parcels_containing, ward_for_point
from .notices import ORDER_KINDS_FINAL, SCN_TYPES, build_notice, dispatch_sms
from .notify import notify_role, notify_user
from .numbering import next_case_no
from .sla import stage_due

S = CaseStatus


class WorkflowError(Exception):
    """Raised for an illegal transition or an unauthorised actor. Rendered as HTTP 400/403."""
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _profile(user) -> OfficerProfile:
    prof = getattr(user, "bvms_profile", None)
    if prof is None or not prof.active:
        raise WorkflowError("User has no active BVMS officer profile", 403)
    return prof


def _authorize(user, action: str, case: ViolationCase | None = None, status: str | None = None) -> OfficerProfile:
    """Check the admin-configurable workflow rules: may this role perform `action` when the case is in
    `status`? Management roles always may. Raises WorkflowError(403) otherwise."""
    prof = _profile(user)
    st = status or (case.status if case is not None else "*")
    if not access.is_action_allowed(st, prof.role, action):
        raise WorkflowError(f"Your role ({prof.get_role_display()}) is not allowed to '{access.ACTION_LABELS.get(action, action)}' while the case is in status {st}", 403)
    return prof


def _require_role(user, *roles):  # kept for backwards compatibility of callers outside this module
    prof = _profile(user)
    if prof.role not in roles and prof.role not in access.MANAGEMENT_ROLES:
        raise WorkflowError(f"Action allowed only for {', '.join(roles)}", 403)
    return prof


def _require_status(case, *statuses):
    if case.status not in statuses:
        raise WorkflowError(f"Case is in status {case.status}; expected one of {', '.join(statuses)}")


def _set_status(case, new_status, user, action, request=None, remarks="", payload=None, owner_role=None):
    old = case.status
    case.status = new_status
    case.status_changed_at = timezone.now()
    case.sla_breached = False
    case.stage_due_at = stage_due(new_status)
    if owner_role:
        case.current_owner_role = owner_role
    case.save()
    record_event(case, action, actor=user, from_status=old, to_status=new_status, remarks=remarks, payload=payload, request=request)


# ---------------------------------------------------------------------------
# 1. Creation (JE / field)
# ---------------------------------------------------------------------------
@transaction.atomic
def create_case(user, data: dict, violation_codes: list[dict], request=None, media_ids: list | None = None) -> ViolationCase:
    prof = _authorize(user, "create", status="*")
    lat, lng = data.get("latitude"), data.get("longitude")
    ward = data.get("ward") or (ward_for_point(lat, lng) if lat and lng else None)
    zone = data.get("zone") or (ward.zone if ward else None) or (prof.zones.first())
    case = ViolationCase(
        case_no=next_case_no(zone.code if zone else None), reported_by=user, ward=ward, zone=zone,
        division=data.get("division") or (ward.division if ward else None),
        current_owner_role=Role.JE, status=S.DRAFT,
    )
    for f in ("source", "complaint_ref", "priority", "pid", "pid_snapshot", "pid_linked_mobile", "alternate_mobile",
              "address_line", "locality", "sector", "village_colony", "pincode", "latitude", "longitude",
              "location_accuracy_m", "land_type", "sanctioned_plan", "owner_name", "owner_father_name",
              "occupier_name", "builder_name", "person_on_site", "construction_stage", "plot_area_sqm",
              "covered_area_sqm", "storeys", "height_m", "use_observed", "description", "measurements", "inspected_at"):
        if f in data and data[f] is not None:
            setattr(case, f, data[f])
    # auto-detect government land
    if lat and lng and case.land_type in (LandType.UNKNOWN, "", None):
        hits = parcels_containing(lat, lng)
        if hits:
            case.govt_parcel = hits[0]
            case.land_type = LandType.GOVT_MCG if hits[0].agency == "MCG" else LandType.GOVT_STATE
        else:
            case.land_type = LandType.PRIVATE
    elif lat and lng and not case.govt_parcel_id:
        hits = parcels_containing(lat, lng)
        if hits:
            case.govt_parcel = hits[0]
    # auto-link sanctioned plan by PID
    if case.pid and not case.sanctioned_plan_id:
        from ..models import SanctionedPlan
        case.sanctioned_plan = SanctionedPlan.objects.filter(pid=case.pid).order_by("-sanctioned_on").first()
    case.save()
    for i, v in enumerate(violation_codes):
        vt = ViolationType.objects.get(code=v["code"])
        CaseViolation.objects.create(case=case, violation_type=vt, details=v.get("details") or {}, remarks=v.get("remarks", ""), is_primary=(i == 0) or bool(v.get("is_primary")))
    if media_ids:
        attach_media(case, media_ids, user)
    record_event(case, "CREATE", actor=user, to_status=S.DRAFT, request=request,
                 payload={"violations": [v["code"] for v in violation_codes], "land_type": case.land_type},
                 lat=case.latitude, lng=case.longitude)
    return case


def attach_media(case: ViolationCase, media_ids: list, user, kind: str | None = None, notice: Notice | None = None):
    qs = MediaAttachment.objects.filter(id__in=media_ids)
    for m in qs:
        m.case = case
        if kind:
            m.kind = kind
        if notice:
            m.notice = notice
        if m.latitude is not None and case.latitude is not None:
            m.distance_from_case_m = round(haversine_m(m.latitude, m.longitude, case.latitude, case.longitude), 2)
            m.geotag_verified = float(m.distance_from_case_m) <= access.geotag_tolerance_m()
        m.save()
    return qs


@transaction.atomic
def update_draft(case, user, data: dict, violation_codes=None, request=None):
    prof = _profile(user)
    if access.has_perm(user, "CASE_EDIT_ANY"):
        pass
    else:
        _authorize(user, "update", case)
        _require_status(case, S.DRAFT, S.RETURNED_TO_JE)
    for f, v in data.items():
        if hasattr(case, f) and f not in ("id", "case_no", "status", "reported_by"):
            setattr(case, f, v)
    case.save()
    if violation_codes is not None:
        case.violations.all().delete()
        for i, v in enumerate(violation_codes):
            CaseViolation.objects.create(case=case, violation_type_id=v["code"], details=v.get("details") or {}, remarks=v.get("remarks", ""), is_primary=(i == 0))
    record_event(case, "UPDATE_DRAFT", actor=user, from_status=case.status, to_status=case.status, request=request, payload={"fields": list(data.keys())})
    return case


@transaction.atomic
def submit_to_ae(case, user, request=None, remarks=""):
    prof = _authorize(user, "submit_to_ae", case)
    _require_status(case, S.DRAFT, S.RETURNED_TO_JE)
    if not case.violations.exists():
        raise WorkflowError("Select at least one violation before submitting")
    if access.get_setting("require_inspection_media", True) and not case.media.filter(kind="INSPECTION").exists():
        raise WorkflowError("Upload at least one geotagged inspection photo/video before submitting")
    case.submitted_at = timezone.now()
    if not access.get_setting("require_ae_review", True):
        # admin switched the AE stage off: straight to the Joint Commissioner
        case.assigned_jc = case.assigned_jc or _pick_jc(case)
        case.jc_received_at = timezone.now()
        _set_status(case, S.PENDING_JC, user, "SUBMIT_TO_JC", request, remarks, owner_role=Role.JC)
        notify_user(case.assigned_jc, case, f"New violation case {case.case_no} for orders", case.address_line)
        return case
    if not case.assigned_ae_id:
        ae = None
        if access.get_setting("auto_assign_ae_by_zone", True) and case.zone_id:
            ae = OfficerProfile.objects.filter(role=Role.AE, active=True, zones=case.zone).first()
        ae = ae or (prof.reports_to if prof.reports_to and prof.reports_to.role == Role.AE else None)
        case.assigned_ae = ae.user if ae else None
    _set_status(case, S.PENDING_AE, user, "SUBMIT_TO_AE", request, remarks, owner_role=Role.AE)
    notify_user(case.assigned_ae, case, f"New violation case {case.case_no} for review", case.address_line)
    if not case.assigned_ae_id:
        notify_role(Role.AE, case, f"Unassigned case {case.case_no} pending AE review", zone=case.zone)
    return case


def _pick_jc(case):
    jc = None
    if access.get_setting("auto_assign_jc_by_zone", True) and case.zone_id:
        jc = OfficerProfile.objects.filter(role=Role.JC, active=True, zones=case.zone).first()
    jc = jc or OfficerProfile.objects.filter(role=Role.JC, active=True).first()
    return jc.user if jc else None


# ---------------------------------------------------------------------------
# 2. AE review
# ---------------------------------------------------------------------------
@transaction.atomic
def ae_forward(case, user, request=None, remarks="", jc_user=None, recommendation=""):
    _authorize(user, "ae_forward", case)
    _require_status(case, S.PENDING_AE)
    if not case.assigned_ae_id:
        case.assigned_ae = user
    if jc_user is None:
        jc_user = _pick_jc(case)
    case.assigned_jc = jc_user
    case.ae_forwarded_at = timezone.now()
    case.jc_received_at = timezone.now()
    _set_status(case, S.PENDING_JC, user, "AE_FORWARD", request, remarks, payload={"recommendation": recommendation}, owner_role=Role.JC)
    notify_user(jc_user, case, f"Case {case.case_no} forwarded by AE for orders", remarks)
    return case


@transaction.atomic
def ae_return(case, user, request=None, remarks=""):
    _authorize(user, "ae_return", case)
    _require_status(case, S.PENDING_AE)
    if not remarks:
        raise WorkflowError("Remarks are mandatory when returning a case")
    _set_status(case, S.RETURNED_TO_JE, user, "AE_RETURN", request, remarks, owner_role=Role.JE)
    notify_user(case.reported_by, case, f"Case {case.case_no} returned for re-inspection", remarks)
    return case


# ---------------------------------------------------------------------------
# 3. JC: notices and orders
# ---------------------------------------------------------------------------
@transaction.atomic
def jc_issue_notice(case, user, request=None, *, order_type_code: str, days: int | None = None, addressee_name: str = "",
                    addressee_address: str = "", mobiles: list[str] | None = None, hearing_at=None, hearing_venue: str = "",
                    operative_text_en: str = "", operative_text_hi: str = "", remarks: str = "", send_sms: bool = True,
                    is_final_order: bool | None = None) -> Notice:
    ot = OrderType.objects.get(code=order_type_code, active=True)
    final_guess = ot.code in ORDER_KINDS_FINAL if is_final_order is None else is_final_order
    prof = _authorize(user, "issue_order" if final_guess else "issue_notice", case)
    if final_guess and access.get_setting("block_final_order_on_pending_referral", True):
        pend = case.referrals.filter(status=BranchReferral.Status.PENDING, hold_case=True).select_related("branch")
        if pend.exists():
            raise WorkflowError("A final order cannot be passed while a 'hold' referral is pending with: " + ", ".join(r.branch.name_en for r in pend))
    allowed = set()
    for cv in case.violations.select_related("violation_type"):
        allowed.update(cv.violation_type.orders_available or [])
    if allowed and ot.code not in allowed and ot.kind in ("NOTICE", "ORDER"):
        raise WorkflowError(f"{ot.code} is not an available action for the violations recorded on this case")
    if ot.kind == "NOTICE":
        _require_status(case, S.PENDING_JC, S.SCN_SERVED, S.RESPONSE_RECEIVED, S.RESPONSE_PENDING_JC, S.NO_RESPONSE, S.HEARING_SCHEDULED, S.SCN_ISSUED)
    if ot.code in ORDER_KINDS_FINAL:
        _require_status(case, S.PENDING_JC, S.RESPONSE_RECEIVED, S.RESPONSE_PENDING_JC, S.NO_RESPONSE, S.HEARING_SCHEDULED, S.SCN_SERVED)
    mobiles = list(mobiles or [])
    for m in (case.pid_linked_mobile, case.alternate_mobile):
        if m and m not in mobiles:
            mobiles.append(m)
    if days is None:
        primary = case.violations.filter(is_primary=True).select_related("violation_type").first() or case.violations.select_related("violation_type").first()
        vt = primary.violation_type if primary else None
        if ot.kind == "NOTICE":
            days = max(ot.default_days, vt.scn_response_days_default if vt else 0)
        elif ot.kind == "ORDER":
            days = max(ot.default_days, vt.order_compliance_days_default if vt else 0)
        else:
            days = 0
    if ot.kind == "NOTICE" and days < ot.min_days:
        raise WorkflowError(f"Statutory minimum response period for {ot.code} is {ot.min_days} days")
    if ot.kind == "ORDER" and days < ot.min_days:
        raise WorkflowError(f"Statutory minimum compliance period for {ot.code} is {ot.min_days} days")
    final = ot.code in ORDER_KINDS_FINAL if is_final_order is None else is_final_order
    n = build_notice(
        case, ot, user, addressee_name=addressee_name, addressee_address=addressee_address, mobiles=mobiles,
        response_days=days if ot.kind == "NOTICE" else 0, compliance_days=days if ot.kind == "ORDER" else 0,
        hearing_at=hearing_at, hearing_venue=hearing_venue, operative_text_en=operative_text_en, operative_text_hi=operative_text_hi,
        is_final_order=final, extra_context={"delegation": {"no": prof.delegation_order_no, "date": prof.delegation_order_date}},
    )
    if send_sms and mobiles:
        dispatch_sms(n)
    # ---- status effects ----
    if ot.code in SCN_TYPES:
        case.scn_issued_at = n.issued_at
        case.response_due_at = n.response_due_at
        if hearing_at:
            case.hearing_at = hearing_at
        _set_status(case, S.SCN_ISSUED, user, "JC_ISSUE_SCN", request, remarks, payload={"notice": n.notice_no, "order_type": ot.code, "days": days}, owner_role=Role.JE)
        notify_user(case.reported_by, case, f"Serve SCN {n.notice_no} for case {case.case_no}", "Deliver the notice and upload geotagged proof of delivery.")
    elif ot.code == "STOP_WORK_262":
        case.stop_work_issued = True
        case.save(update_fields=["stop_work_issued"])
        record_event(case, "JC_ISSUE_STOP_WORK", actor=user, from_status=case.status, to_status=case.status, remarks=remarks, payload={"notice": n.notice_no}, request=request)
        notify_user(case.reported_by, case, f"Stop-work order {n.notice_no} issued - serve and enforce", remarks)
    elif ot.code in ("SEALING_263A", "RESEALING_263A") and not final:
        case.sealed = True
        case.save(update_fields=["sealed"])
        record_event(case, "JC_ISSUE_SEALING", actor=user, from_status=case.status, to_status=case.status, remarks=remarks, payload={"notice": n.notice_no}, request=request)
        notify_user(case.reported_by, case, f"Sealing order {n.notice_no} issued - execute sealing and upload evidence", remarks)
    elif final:
        case.decided_at = timezone.now()
        case.decision = {"DEMOLITION_ORDER_261": "DEMOLITION", "EVICTION_DEMOLITION_ORDER_408A": "EVICTION", "DEMOLITION_ORDER_284": "DEMOLITION",
                         "SEALING_263A": "SEALING", "DANGEROUS_BUILDING_ORDER_265": "DEMOLITION", "VACATE_ORDER_266": "VACATE", "OC_REVOCATION_HBC_4_12": "OC_REVOKED"}.get(ot.code, ot.code)
        case.decision_reasons = remarks or case.decision_reasons
        case.final_order = n
        case.order_issued_at = n.issued_at
        case.compliance_due_at = n.compliance_due_at
        if ot.code == "SEALING_263A":
            case.sealed = True
        _set_status(case, S.ORDER_ISSUED, user, "JC_ISSUE_FINAL_ORDER", request, remarks, payload={"notice": n.notice_no, "order_type": ot.code, "days": days}, owner_role=Role.JE)
        notify_user(case.reported_by, case, f"Final order {n.notice_no} for case {case.case_no} - serve and upload proof", remarks)
        notify_role(Role.FIELD_STAFF, case, f"Order {n.notice_no}: execution due after {days} days", zone=case.zone)
    else:  # memos / referrals
        record_event(case, "JC_ISSUE_MEMO", actor=user, from_status=case.status, to_status=case.status, remarks=remarks, payload={"notice": n.notice_no, "order_type": ot.code}, request=request)
    return n


@transaction.atomic
def jc_drop(case, user, request=None, remarks="", regularised=False):
    _authorize(user, "regularise" if regularised else "drop", case)
    _require_status(case, S.PENDING_JC, S.SCN_SERVED, S.RESPONSE_RECEIVED, S.RESPONSE_PENDING_JC, S.NO_RESPONSE, S.HEARING_SCHEDULED, S.SCN_ISSUED, S.ORDER_SERVED, S.APPEAL_STAY, S.EXECUTION_DUE)
    if not remarks:
        raise WorkflowError("A speaking order / reasons are mandatory to drop or regularise a case")
    case.decided_at = timezone.now()
    case.decision = "REGULARISE" if regularised else "DROP"
    case.decision_reasons = remarks
    case.closed_at = timezone.now()
    _set_status(case, S.REGULARISED if regularised else S.DROPPED, user, "JC_REGULARISE" if regularised else "JC_DROP", request, remarks, owner_role=Role.JC)
    notify_user(case.reported_by, case, f"Case {case.case_no} {'regularised' if regularised else 'dropped'} by JC", remarks)
    return case


# ---------------------------------------------------------------------------
# 4. Service of notice / order (field)
# ---------------------------------------------------------------------------
@transaction.atomic
def record_service(notice: Notice, user, request=None, *, mode: str, served_at=None, remarks: str = "", media_ids: list | None = None):
    case = notice.case
    _authorize(user, "record_service", case)
    if mode == "AFFIXATION" and not media_ids and access.get_setting("require_geotag_for_affixation", True):
        raise WorkflowError("Affixation must be proved by at least one geotagged photograph")
    if media_ids:
        attach_media(case, media_ids, user, kind="NOTICE_DELIVERY" if notice.kind == "NOTICE" else "ORDER_DELIVERY", notice=notice)
        bad = [str(m.id) for m in notice.media.all() if m.latitude is not None and not m.geotag_verified]
        if bad and case.latitude is not None:
            raise WorkflowError("Delivery-proof photograph(s) were captured away from the property location; retake at the site")
    notice.served_at = served_at or timezone.now()
    notice.served_mode = mode
    notice.served_by = user
    notice.service_remarks = remarks
    notice.save()
    if notice.order_type.code in SCN_TYPES and case.status == S.SCN_ISSUED:
        case.scn_served_at = notice.served_at
        # statutory clock runs from service (s.408A(1): "from the date of service of the notice")
        if notice.response_days:
            notice.response_due_at = notice.served_at + timedelta(days=notice.response_days)
            notice.save(update_fields=["response_due_at"])
            case.response_due_at = notice.response_due_at
        _set_status(case, S.SCN_SERVED, user, "SCN_SERVED", request, remarks, payload={"notice": notice.notice_no, "mode": mode}, owner_role=Role.JC)
    elif notice.is_final_order and case.status == S.ORDER_ISSUED:
        case.order_served_at = notice.served_at
        if notice.compliance_days:
            notice.compliance_due_at = notice.served_at + timedelta(days=notice.compliance_days)
            notice.save(update_fields=["compliance_due_at"])
            case.compliance_due_at = notice.compliance_due_at
        _set_status(case, S.ORDER_SERVED, user, "ORDER_SERVED", request, remarks, payload={"notice": notice.notice_no, "mode": mode, "compliance_due_at": str(case.compliance_due_at)}, owner_role=Role.FIELD_STAFF)
    else:
        record_event(case, "NOTICE_SERVED", actor=user, from_status=case.status, to_status=case.status, remarks=remarks, payload={"notice": notice.notice_no, "mode": mode}, request=request)
    return notice


# ---------------------------------------------------------------------------
# 5. Response of the noticee
# ---------------------------------------------------------------------------
@transaction.atomic
def record_response(case, user, request=None, *, notice: Notice | None, received_on, received_via: str, summary: str,
                    submitted_by_name: str = "", requests_hearing: bool = False, media_ids: list | None = None, remarks=""):
    prof = _authorize(user, "record_response", case)
    _require_status(case, S.SCN_SERVED, S.SCN_ISSUED, S.NO_RESPONSE, S.HEARING_SCHEDULED, S.RESPONSE_RECEIVED, S.RESPONSE_PENDING_AE, S.RESPONSE_PENDING_JC)
    notice = notice or case.notices.filter(order_type__code__in=SCN_TYPES).order_by("-issued_at").first()
    within = True
    if notice and notice.response_due_at:
        within = timezone.make_aware(timezone.datetime.combine(received_on, timezone.datetime.min.time())) <= notice.response_due_at + timedelta(days=1)
    resp = CaseResponse.objects.create(case=case, notice=notice, received_on=received_on, received_via=received_via or prof.role,
                                       submitted_by_name=submitted_by_name, summary=summary, requests_hearing=requests_hearing,
                                       is_within_time=within, uploaded_by=user)
    if media_ids:
        attach_media(case, media_ids, user, kind="RESPONSE")
    case.response_received_at = timezone.now()
    # Route: JE-uploaded responses travel via AE to JC (configurable); clerk/JC uploads go straight to JC.
    if prof.role in (Role.JE, Role.FIELD_STAFF) and access.get_setting("route_je_response_via_ae", True) and access.get_setting("require_ae_review", True):
        _set_status(case, S.RESPONSE_PENDING_AE, user, "RESPONSE_RECORDED", request, remarks, payload={"response_id": resp.id, "via": received_via}, owner_role=Role.AE)
        notify_user(case.assigned_ae, case, f"Response received on {case.case_no} - add comments and forward", summary[:200])
    else:
        _set_status(case, S.RESPONSE_PENDING_JC, user, "RESPONSE_RECORDED", request, remarks, payload={"response_id": resp.id, "via": received_via}, owner_role=Role.JC)
        notify_user(case.assigned_jc, case, f"Response received on {case.case_no} - decision pending", summary[:200])
    return resp


@transaction.atomic
def ae_forward_response(response: CaseResponse, user, request=None, comments=""):
    case = response.case
    _authorize(user, "ae_forward_response", case)
    _require_status(case, S.RESPONSE_PENDING_AE)
    response.ae_comments = comments
    response.ae_commented_at = timezone.now()
    response.save()
    _set_status(case, S.RESPONSE_PENDING_JC, user, "AE_FORWARD_RESPONSE", request, comments, payload={"response_id": response.id}, owner_role=Role.JC)
    notify_user(case.assigned_jc, case, f"Response on {case.case_no} forwarded with AE comments", comments[:200])
    return response


@transaction.atomic
def mark_no_response(case, actor=None):
    if case.status != S.SCN_SERVED or not case.response_due_at or case.response_due_at > timezone.now():
        return case
    _set_status(case, S.NO_RESPONSE, actor, "NO_RESPONSE_DEADLINE", None, "Response period expired without reply", owner_role=Role.JC)
    notify_user(case.assigned_jc, case, f"No response on {case.case_no} - period expired", "Decide ex parte or fix a hearing.")
    return case


# ---------------------------------------------------------------------------
# 6. Hearing
# ---------------------------------------------------------------------------
@transaction.atomic
def schedule_hearing(case, user, request=None, *, scheduled_at, venue="", notice: Notice | None = None, remarks=""):
    prof = _authorize(user, "schedule_hearing", case)
    if prof.role == Role.JC_CLERK and not access.get_setting("allow_jc_clerk_hearing", True):
        raise WorkflowError("Clerks are not allowed to fix hearings (workflow setting)", 403)
    _require_status(case, S.SCN_SERVED, S.RESPONSE_RECEIVED, S.RESPONSE_PENDING_JC, S.NO_RESPONSE, S.HEARING_SCHEDULED, S.RESPONSE_PENDING_AE)
    presiding = case.assigned_jc or user
    h = Hearing.objects.create(case=case, notice=notice, scheduled_at=scheduled_at, venue=venue, presiding=presiding)
    case.hearing_at = scheduled_at
    _set_status(case, S.HEARING_SCHEDULED, user, "HEARING_SCHEDULED", request, remarks, payload={"hearing_id": h.id, "at": str(scheduled_at)}, owner_role=Role.JC)
    notify_user(case.reported_by, case, f"Hearing fixed on {case.case_no}", f"{scheduled_at:%d-%m-%Y %H:%M} at {venue}. Inform the noticee.")
    return h


@transaction.atomic
def record_hearing(hearing: Hearing, user, request=None, *, proceedings="", attendees="", outcome="HEARD", next_date=None, media_ids=None):
    _authorize(user, "record_hearing", hearing.case)
    hearing.held_at = timezone.now()
    hearing.proceedings, hearing.attendees, hearing.outcome, hearing.next_date = proceedings, attendees, outcome, next_date
    hearing.save()
    case = hearing.case
    if media_ids:
        attach_media(case, media_ids, user, kind="HEARING")
    if outcome == "ADJOURNED" and next_date:
        case.hearing_at = next_date
        Hearing.objects.create(case=case, notice=hearing.notice, scheduled_at=next_date, venue=hearing.venue, presiding=hearing.presiding)
        record_event(case, "HEARING_ADJOURNED", actor=user, from_status=case.status, to_status=case.status, remarks=proceedings, payload={"next_date": str(next_date)}, request=request)
    else:
        _set_status(case, S.RESPONSE_PENDING_JC, user, "HEARING_HELD", request, proceedings, payload={"hearing_id": hearing.id, "outcome": outcome}, owner_role=Role.JC)
    return hearing


# ---------------------------------------------------------------------------
# 7. Appeal / stay
# ---------------------------------------------------------------------------
def _sync_litigation_flag(case: ViolationCase):
    """Mirror the latest live appeal on the case so lists, dashboards and the app show the flag."""
    ap = case.appeals.order_by("-filed_on", "-id").first()
    if not ap:
        case.litigation_status, case.litigation_authority, case.stay_until, case.next_hearing_on = "NONE", "", None, None
    else:
        case.litigation_authority = ap.authority
        case.next_hearing_on = ap.next_hearing_on
        if ap.status == Appeal.Status.STAYED:
            case.litigation_status, case.stay_until = "STAYED", ap.stay_until
        elif ap.status == Appeal.Status.PENDING:
            case.litigation_status, case.stay_until = "APPEAL_PENDING", None
        else:
            case.litigation_status, case.stay_until = "DECIDED", None
    case.save(update_fields=["litigation_status", "litigation_authority", "stay_until", "next_hearing_on"])


@transaction.atomic
def record_appeal(case, user, request=None, *, filed_on, authority, appeal_no="", authority_other="", appellant_name="", counsel_for_mcg="",
                  stay_granted=False, stay_order_date=None, stay_until=None, stay_scope="", conditions="", next_hearing_on=None,
                  stay_order_media=None, order: Notice | None = None, media_ids=None, remarks=""):
    """Record an appeal / writ. A stay may be recorded only with the stay order uploaded (setting
    `require_stay_order_upload`), so that every deferred action has a legal backing on the file."""
    _authorize(user, "record_appeal", case)
    if stay_granted and access.get_setting("require_stay_order_upload", True) and not stay_order_media:
        raise WorkflowError("Upload the stay / interim order before recording a stay - a deferred action must have the court's order on file")
    ap = Appeal.objects.create(case=case, order=order or case.final_order, authority=authority, authority_other=authority_other, filed_on=filed_on, appeal_no=appeal_no,
                               appellant_name=appellant_name or case.owner_name, counsel_for_mcg=counsel_for_mcg,
                               status=Appeal.Status.STAYED if stay_granted else Appeal.Status.PENDING, stay_granted=stay_granted, stay_order_date=stay_order_date,
                               stay_until=stay_until, stay_scope=stay_scope or (Appeal.StayScope.FULL if stay_granted else ""), conditions=conditions,
                               next_hearing_on=next_hearing_on, stay_order=stay_order_media, recorded_by=user)
    if media_ids:
        attach_media(case, media_ids, user, kind="APPEAL")
    if stay_order_media:
        stay_order_media.case = case
        stay_order_media.kind = "STAY_ORDER"
        stay_order_media.save(update_fields=["case", "kind"])
    _sync_litigation_flag(case)
    payload = {"appeal_id": ap.id, "authority": authority, "appeal_no": appeal_no, "stay": stay_granted, "stay_until": str(stay_until) if stay_until else None, "stay_order_media": str(stay_order_media.id) if stay_order_media else None}
    if stay_granted:
        _set_status(case, S.APPEAL_STAY, user, "APPEAL_STAY", request, remarks or f"Stay by {ap.get_authority_display()} ({appeal_no})", payload=payload, owner_role=Role.JC)
        notify_user(case.reported_by, case, f"STAY on {case.case_no} by {ap.get_authority_display()}", "No further action till the stay is vacated / expires. Order is on the case file.")
        notify_role(Role.FIELD_STAFF, case, f"STAY on {case.case_no} - do not execute", zone=case.zone, level="WARNING")
    else:
        record_event(case, "APPEAL_FILED", actor=user, from_status=case.status, to_status=case.status, remarks=remarks, payload=payload, request=request)
    notify_user(case.assigned_jc, case, f"Appeal recorded on {case.case_no} before {ap.get_authority_display()}", appeal_no)
    return ap


@transaction.atomic
def update_appeal(appeal: Appeal, user, request=None, *, status: str | None = None, decided_on=None, decision_summary="", new_compliance_days: int | None = None,
                  stay_until=None, stay_scope=None, conditions=None, next_hearing_on=None, stay_order_media=None, final_order_media=None, appeal_no=None,
                  counsel_for_mcg=None, media_ids=None, remarks=""):
    """Update the litigation flag: extend / vacate a stay, record hearing dates, upload later orders,
    record the final decision. Resumes the compliance clock when the stay goes."""
    _authorize(user, "decide_appeal", appeal.case)
    case = appeal.case
    before = appeal.status
    if media_ids:
        attach_media(case, media_ids, user, kind="APPEAL")
    if stay_order_media:
        stay_order_media.case, stay_order_media.kind = case, "STAY_ORDER"
        stay_order_media.save(update_fields=["case", "kind"])
        appeal.stay_order = stay_order_media
    if final_order_media:
        final_order_media.case, final_order_media.kind = case, "COURT_ORDER"
        final_order_media.save(update_fields=["case", "kind"])
        appeal.final_order = final_order_media
    if status:
        if status == Appeal.Status.STAYED and not appeal.stay_order and access.get_setting("require_stay_order_upload", True):
            raise WorkflowError("Upload the stay / interim order before recording a stay")
        appeal.status = status
        appeal.stay_granted = status == Appeal.Status.STAYED
    for f, v in (("stay_until", stay_until), ("stay_scope", stay_scope), ("conditions", conditions), ("next_hearing_on", next_hearing_on), ("appeal_no", appeal_no), ("counsel_for_mcg", counsel_for_mcg)):
        if v is not None:
            setattr(appeal, f, v)
    if decided_on:
        appeal.decided_on = decided_on
    if decision_summary:
        appeal.decision_summary = decision_summary
    appeal.save()
    _sync_litigation_flag(case)
    payload = {"appeal_id": appeal.id, "from": before, "to": appeal.status, "stay_until": str(appeal.stay_until) if appeal.stay_until else None, "next_hearing_on": str(appeal.next_hearing_on) if appeal.next_hearing_on else None}
    stay_lifted = before == Appeal.Status.STAYED and appeal.status in (Appeal.Status.STAY_VACATED, Appeal.Status.DISMISSED, Appeal.Status.MODIFIED, Appeal.Status.WITHDRAWN, Appeal.Status.DISPOSED)
    if stay_lifted and case.status == S.APPEAL_STAY:
        if new_compliance_days:
            case.compliance_due_at = timezone.now() + timedelta(days=new_compliance_days)
        elif case.compliance_due_at and case.compliance_due_at < timezone.now():
            case.compliance_due_at = timezone.now() + timedelta(days=3)  # residual period, never below the statutory minimum
        _set_status(case, S.ORDER_SERVED if case.order_served_at else S.PENDING_JC, user, "STAY_LIFTED", request, decision_summary or remarks, payload=payload, owner_role=Role.FIELD_STAFF if case.order_served_at else Role.JC)
        notify_user(case.reported_by, case, f"Stay lifted on {case.case_no} - compliance clock resumed", f"Comply by {case.compliance_due_at:%d-%m-%Y}" if case.compliance_due_at else "")
    elif appeal.status == Appeal.Status.STAYED and case.status != S.APPEAL_STAY and case.status not in (S.CLOSED, S.DROPPED, S.REGULARISED):
        _set_status(case, S.APPEAL_STAY, user, "APPEAL_STAY", request, remarks, payload=payload, owner_role=Role.JC)
    elif appeal.status == Appeal.Status.ALLOWED:
        case.closure_reason = f"Order set aside by {appeal.get_authority_display()}: {decision_summary}"
        case.closed_at = timezone.now()
        _set_status(case, S.CLOSED, user, "APPEAL_ALLOWED", request, decision_summary, payload=payload, owner_role=Role.JC)
    else:
        record_event(case, "APPEAL_UPDATED", actor=user, from_status=case.status, to_status=case.status, remarks=decision_summary or remarks, payload=payload, request=request)
    return appeal


def decide_appeal(appeal: Appeal, user, request=None, *, status: str, decided_on, decision_summary="", new_compliance_days: int | None = None, media_ids=None):
    """Backwards-compatible wrapper around update_appeal."""
    return update_appeal(appeal, user, request, status=status, decided_on=decided_on, decision_summary=decision_summary, new_compliance_days=new_compliance_days, media_ids=media_ids)


# ---------------------------------------------------------------------------
# 8. Compliance / execution
# ---------------------------------------------------------------------------
@transaction.atomic
def mark_execution_due(case, actor=None):
    if case.status != S.ORDER_SERVED or not case.compliance_due_at or case.compliance_due_at > timezone.now():
        return case
    _set_status(case, S.EXECUTION_DUE, actor, "COMPLIANCE_PERIOD_EXPIRED", None, "Compliance period over; execution by the Corporation due", owner_role=Role.FIELD_STAFF)
    notify_user(case.reported_by, case, f"Execution due: {case.case_no}", "Compliance period has expired. Carry out demolition/sealing and upload geotagged evidence.")
    notify_role(Role.FIELD_STAFF, case, f"Execution due: {case.case_no}", zone=case.zone)
    notify_user(case.assigned_jc, case, f"Execution due: {case.case_no}", "")
    return case


@transaction.atomic
def record_execution(case, user, request=None, *, action: str, mode: str, executed_on, media_ids: list, squad_incharge="", police_assistance=False,
                     police_station="", duty_magistrate="", machinery_used="", area_demolished_sqm=None, seal_memo_no="", cost_incurred_inr=None, remarks=""):
    _authorize(user, "record_execution", case)
    _require_status(case, S.ORDER_SERVED, S.EXECUTION_DUE, S.ORDER_ISSUED, S.PENDING_JC, S.SCN_SERVED, S.RESPONSE_PENDING_JC, S.NO_RESPONSE)
    if not media_ids:
        raise WorkflowError("Geotagged photographs/videos of the demolition or sealing are mandatory")
    attach_media(case, media_ids, user, kind="EXECUTION" if mode == "CORPORATION" else "COMPLIANCE")
    unverified = case.media.filter(id__in=media_ids, geotag_verified=False, latitude__isnull=False)
    if access.get_setting("require_geotag_for_execution", True) and case.latitude is not None and unverified.exists():
        raise WorkflowError("Execution evidence must be captured at the property location (geotag mismatch)")
    ex = ExecutionRecord.objects.create(case=case, order=case.final_order, action=action, mode=mode, executed_on=executed_on, squad_incharge=squad_incharge,
                                        police_assistance=police_assistance, police_station=police_station, duty_magistrate=duty_magistrate,
                                        machinery_used=machinery_used, area_demolished_sqm=area_demolished_sqm, seal_memo_no=seal_memo_no,
                                        cost_incurred_inr=cost_incurred_inr, remarks=remarks, recorded_by=user)
    case.executed_at = executed_on
    if action == "SEALING":
        case.sealed = True
    if action == "DESEALING":
        case.sealed = False
    if cost_incurred_inr:
        case.demolition_cost_inr = cost_incurred_inr
        case.cost_recovery_status = "PENDING"
    new_status = S.COMPLIED if mode == "OWNER_SELF" else S.EXECUTED
    if action in ("SEALING", "DESEALING") and case.status not in (S.ORDER_SERVED, S.EXECUTION_DUE):
        record_event(case, "EXECUTION_RECORDED", actor=user, from_status=case.status, to_status=case.status, remarks=remarks, payload={"execution_id": ex.id, "action": action}, request=request)
    else:
        _set_status(case, new_status, user, "EXECUTION_RECORDED", request, remarks, payload={"execution_id": ex.id, "action": action, "mode": mode}, owner_role=Role.JC)
    notify_user(case.assigned_jc, case, f"{action.title()} recorded on {case.case_no} - verify and close", remarks)
    return ex


@transaction.atomic
def verify_and_close(case, user, request=None, remarks=""):
    _authorize(user, "close", case)
    _require_status(case, S.COMPLIED, S.EXECUTED, S.DROPPED, S.REGULARISED)
    ex = case.executions.order_by("-executed_on").first()
    if ex and not ex.verified_at:
        ex.verified_by, ex.verified_at = user, timezone.now()
        ex.save(update_fields=["verified_by", "verified_at"])
    case.closed_at = timezone.now()
    case.closure_reason = remarks or case.closure_reason
    _set_status(case, S.CLOSED, user, "CLOSE", request, remarks, owner_role=Role.JC)
    return case


@transaction.atomic
def reopen(case, user, request=None, remarks=""):
    _authorize(user, "reopen", case)
    _require_status(case, S.CLOSED, S.DROPPED, S.REGULARISED)
    if not remarks:
        raise WorkflowError("Reasons are mandatory to reopen a case")
    case.closed_at = None
    _set_status(case, S.PENDING_JC, user, "REOPEN", request, remarks, owner_role=Role.JC)
    return case


# ---------------------------------------------------------------------------
# 9. Branch referrals (Planning / Revenue / Legal ...) and re-assignment
# ---------------------------------------------------------------------------
@transaction.atomic
def refer_to_branch(case, user, request=None, *, branch: Branch, query: str, due_days: int | None = None, hold_case: bool = False, assigned_to=None, media_ids=None, remarks=""):
    """Send the case to a branch for its report. The main workflow status is unchanged; the referral is
    tracked separately and (optionally) blocks the final order until answered."""
    _authorize(user, "refer_branch", case)
    if not access.has_perm(user, "BRANCH_REFER"):
        raise WorkflowError("You do not have the BRANCH_REFER permission", 403)
    if not query.strip():
        raise WorkflowError("State what the branch is asked to examine")
    if case.status in (S.CLOSED, S.DROPPED, S.REGULARISED):
        raise WorkflowError("Closed cases cannot be referred")
    days = due_days if due_days is not None else (branch.default_response_days or access.get_setting("referral_default_days", 7))
    ref = BranchReferral.objects.create(case=case, branch=branch, referred_by=user, query=query, due_at=timezone.now() + timedelta(days=int(days)),
                                        hold_case=hold_case, assigned_to=assigned_to)
    if media_ids:
        attach_media(case, media_ids, user, kind="BRANCH_REFERRAL")
    record_event(case, "REFERRED_TO_BRANCH", actor=user, from_status=case.status, to_status=case.status, remarks=f"{branch.name_en}: {query}", payload={"referral_id": ref.id, "branch": branch.code, "hold_case": hold_case, "due_at": str(ref.due_at)}, request=request)
    if assigned_to:
        notify_user(assigned_to, case, f"Referral on {case.case_no} - {branch.name_en}", query[:200])
    else:
        for p in OfficerProfile.objects.filter(role=Role.BRANCH_OFFICER, branch=branch, active=True):
            notify_user(p.user, case, f"Referral on {case.case_no} - {branch.name_en}", query[:200])
    return ref


@transaction.atomic
def respond_to_referral(ref: BranchReferral, user, request=None, *, response: str, recommendation: str = "", media_ids=None):
    case = ref.case
    prof = _authorize(user, "respond_branch", case)
    if prof.role == Role.BRANCH_OFFICER and prof.branch_id != ref.branch_id and not access.has_perm(user, "REFERRALS_VIEW_ALL"):
        raise WorkflowError("This referral belongs to another branch", 403)
    if ref.status != BranchReferral.Status.PENDING:
        raise WorkflowError("This referral has already been answered / closed")
    if not response.strip():
        raise WorkflowError("Enter the branch's response")
    ref.response, ref.recommendation, ref.responded_by, ref.responded_at = response, recommendation, user, timezone.now()
    ref.status = BranchReferral.Status.RESPONDED
    ref.save()
    if media_ids:
        attach_media(case, media_ids, user, kind="BRANCH_RESPONSE")
    record_event(case, "BRANCH_RESPONDED", actor=user, from_status=case.status, to_status=case.status, remarks=f"{ref.branch.name_en}: {response}", payload={"referral_id": ref.id, "branch": ref.branch.code, "recommendation": recommendation}, request=request)
    notify_user(ref.referred_by, case, f"{ref.branch.name_en} has responded on {case.case_no}", response[:200])
    if case.assigned_jc_id and case.assigned_jc_id != ref.referred_by_id:
        notify_user(case.assigned_jc, case, f"{ref.branch.name_en} has responded on {case.case_no}", response[:200])
    return ref


@transaction.atomic
def close_referral(ref: BranchReferral, user, request=None, *, remarks="", withdrawn=False):
    case = ref.case
    _authorize(user, "refer_branch", case)
    if ref.referred_by_id != user.pk and not access.has_perm(user, "REFERRALS_VIEW_ALL") and getattr(user, "bvms_profile", None) and user.bvms_profile.role not in access.MANAGEMENT_ROLES:
        raise WorkflowError("Only the referring officer can close this referral", 403)
    ref.status = BranchReferral.Status.WITHDRAWN if withdrawn else BranchReferral.Status.CLOSED
    ref.closed_by, ref.closed_at, ref.closing_remarks = user, timezone.now(), remarks
    ref.save()
    record_event(case, "REFERRAL_WITHDRAWN" if withdrawn else "REFERRAL_CLOSED", actor=user, from_status=case.status, to_status=case.status, remarks=remarks, payload={"referral_id": ref.id}, request=request)
    return ref


@transaction.atomic
def reassign_case(case, user, request=None, *, assigned_ae=None, assigned_jc=None, reported_by=None, remarks="", order_reference=""):
    """Change the officers handling a case (used when jurisdictions change or an officer is transferred)."""
    _authorize(user, "reassign", case)
    if not access.has_perm(user, "CASE_REASSIGN"):
        raise WorkflowError("You do not have the CASE_REASSIGN permission", 403)
    before = {"ae": case.assigned_ae_id, "jc": case.assigned_jc_id, "je": case.reported_by_id}
    if assigned_ae is not None:
        case.assigned_ae = assigned_ae
    if assigned_jc is not None:
        case.assigned_jc = assigned_jc
    if reported_by is not None:
        case.reported_by = reported_by
    case.save()
    after = {"ae": case.assigned_ae_id, "jc": case.assigned_jc_id, "je": case.reported_by_id}
    record_event(case, "REASSIGNED", actor=user, from_status=case.status, to_status=case.status, remarks=remarks or order_reference, payload={"before": before, "after": after, "order_reference": order_reference}, request=request)
    for u in (assigned_ae, assigned_jc, reported_by):
        if u is not None:
            notify_user(u, case, f"Case {case.case_no} assigned to you", remarks)
    return case


def available_actions(case, user) -> list[str]:
    """Actions the UI may offer this user on this case (DB-driven rules + per-case guards)."""
    prof = getattr(user, "bvms_profile", None)
    if not prof or not prof.active:
        return []
    acts = set(access.actions_for(case.status, prof.role))
    if "respond_branch" in acts:
        pend = case.referrals.filter(status=BranchReferral.Status.PENDING)
        if prof.role == Role.BRANCH_OFFICER and not access.has_perm(user, "REFERRALS_VIEW_ALL"):
            pend = pend.filter(branch=prof.branch)
        if not pend.exists():
            acts.discard("respond_branch")
    if "refer_branch" in acts and (case.status in (S.CLOSED, S.DROPPED, S.REGULARISED) or not access.has_perm(user, "BRANCH_REFER")):
        acts.discard("refer_branch")
    if "reassign" in acts and not access.has_perm(user, "CASE_REASSIGN"):
        acts.discard("reassign")
    if "create" in acts:
        acts.discard("create")
    return sorted(acts)


# Backwards-compatible alias for code that imported the static matrix
ACTION_MATRIX = access.DEFAULT_ACTION_MATRIX
