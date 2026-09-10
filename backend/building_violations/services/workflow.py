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
    Appeal, CaseResponse, CaseStatus, CaseViolation, ExecutionRecord, Hearing, LandType, MediaAttachment, Notice,
    OfficerProfile, OrderType, Role, ViolationCase, ViolationType,
)
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


def _require_role(user, *roles):
    prof = _profile(user)
    if prof.role not in roles and prof.role not in (Role.ADMIN, Role.COMMISSIONER, Role.ADDL_COMMISSIONER):
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
    prof = _require_role(user, Role.JE, Role.AE, Role.FIELD_STAFF)
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
            from django.conf import settings
            m.geotag_verified = float(m.distance_from_case_m) <= settings.BVMS_GEOTAG_TOLERANCE_M
        m.save()
    return qs


@transaction.atomic
def update_draft(case, user, data: dict, violation_codes=None, request=None):
    _require_role(user, Role.JE, Role.AE)
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
    prof = _require_role(user, Role.JE, Role.FIELD_STAFF)
    _require_status(case, S.DRAFT, S.RETURNED_TO_JE)
    if not case.violations.exists():
        raise WorkflowError("Select at least one violation before submitting")
    if not case.media.filter(kind="INSPECTION").exists():
        raise WorkflowError("Upload at least one geotagged inspection photo/video before submitting")
    if not case.assigned_ae_id:
        ae = OfficerProfile.objects.filter(role=Role.AE, active=True, zones=case.zone).first() if case.zone_id else None
        ae = ae or (prof.reports_to if prof.reports_to and prof.reports_to.role == Role.AE else None)
        case.assigned_ae = ae.user if ae else None
    case.submitted_at = timezone.now()
    _set_status(case, S.PENDING_AE, user, "SUBMIT_TO_AE", request, remarks, owner_role=Role.AE)
    notify_user(case.assigned_ae, case, f"New violation case {case.case_no} for review", case.address_line)
    if not case.assigned_ae_id:
        notify_role(Role.AE, case, f"Unassigned case {case.case_no} pending AE review", zone=case.zone)
    return case


# ---------------------------------------------------------------------------
# 2. AE review
# ---------------------------------------------------------------------------
@transaction.atomic
def ae_forward(case, user, request=None, remarks="", jc_user=None, recommendation=""):
    _require_role(user, Role.AE, Role.XEN)
    _require_status(case, S.PENDING_AE)
    if not case.assigned_ae_id:
        case.assigned_ae = user
    if jc_user is None:
        jc = OfficerProfile.objects.filter(role=Role.JC, active=True, zones=case.zone).first() if case.zone_id else None
        jc = jc or OfficerProfile.objects.filter(role=Role.JC, active=True).first()
        jc_user = jc.user if jc else None
    case.assigned_jc = jc_user
    case.ae_forwarded_at = timezone.now()
    case.jc_received_at = timezone.now()
    _set_status(case, S.PENDING_JC, user, "AE_FORWARD", request, remarks, payload={"recommendation": recommendation}, owner_role=Role.JC)
    notify_user(jc_user, case, f"Case {case.case_no} forwarded by AE for orders", remarks)
    return case


@transaction.atomic
def ae_return(case, user, request=None, remarks=""):
    _require_role(user, Role.AE, Role.XEN)
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
    prof = _require_role(user, Role.JC)
    ot = OrderType.objects.get(code=order_type_code, active=True)
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
    _require_role(user, Role.JC)
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
    _require_role(user, Role.JE, Role.FIELD_STAFF, Role.AE, Role.JC, Role.JC_CLERK)
    case = notice.case
    if mode == "AFFIXATION" and not media_ids:
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
    prof = _require_role(user, Role.JE, Role.JC_CLERK, Role.AE, Role.JC)
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
    # Route: JE-uploaded responses travel via AE to JC; clerk/JC uploads go straight to JC.
    if prof.role in (Role.JE, Role.FIELD_STAFF):
        _set_status(case, S.RESPONSE_PENDING_AE, user, "RESPONSE_RECORDED", request, remarks, payload={"response_id": resp.id, "via": received_via}, owner_role=Role.AE)
        notify_user(case.assigned_ae, case, f"Response received on {case.case_no} - add comments and forward", summary[:200])
    else:
        _set_status(case, S.RESPONSE_PENDING_JC, user, "RESPONSE_RECORDED", request, remarks, payload={"response_id": resp.id, "via": received_via}, owner_role=Role.JC)
        notify_user(case.assigned_jc, case, f"Response received on {case.case_no} - decision pending", summary[:200])
    return resp


@transaction.atomic
def ae_forward_response(response: CaseResponse, user, request=None, comments=""):
    _require_role(user, Role.AE, Role.XEN)
    case = response.case
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
    _require_role(user, Role.JC, Role.JC_CLERK)
    _require_status(case, S.SCN_SERVED, S.RESPONSE_RECEIVED, S.RESPONSE_PENDING_JC, S.NO_RESPONSE, S.HEARING_SCHEDULED, S.RESPONSE_PENDING_AE)
    presiding = case.assigned_jc or user
    h = Hearing.objects.create(case=case, notice=notice, scheduled_at=scheduled_at, venue=venue, presiding=presiding)
    case.hearing_at = scheduled_at
    _set_status(case, S.HEARING_SCHEDULED, user, "HEARING_SCHEDULED", request, remarks, payload={"hearing_id": h.id, "at": str(scheduled_at)}, owner_role=Role.JC)
    notify_user(case.reported_by, case, f"Hearing fixed on {case.case_no}", f"{scheduled_at:%d-%m-%Y %H:%M} at {venue}. Inform the noticee.")
    return h


@transaction.atomic
def record_hearing(hearing: Hearing, user, request=None, *, proceedings="", attendees="", outcome="HEARD", next_date=None, media_ids=None):
    _require_role(user, Role.JC, Role.JC_CLERK)
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
@transaction.atomic
def record_appeal(case, user, request=None, *, filed_on, authority, appeal_no="", stay_granted=False, stay_until=None, conditions="", order: Notice | None = None, media_ids=None, remarks=""):
    _require_role(user, Role.JC, Role.JC_CLERK, Role.AE)
    ap = Appeal.objects.create(case=case, order=order or case.final_order, filed_on=filed_on, authority=authority, appeal_no=appeal_no,
                               status="STAYED" if stay_granted else "PENDING", stay_granted=stay_granted, stay_until=stay_until,
                               conditions=conditions, recorded_by=user)
    if media_ids:
        attach_media(case, media_ids, user, kind="APPEAL")
    if stay_granted:
        _set_status(case, S.APPEAL_STAY, user, "APPEAL_STAY", request, remarks, payload={"appeal_id": ap.id, "authority": authority, "stay_until": str(stay_until)}, owner_role=Role.JC)
    else:
        record_event(case, "APPEAL_FILED", actor=user, from_status=case.status, to_status=case.status, remarks=remarks, payload={"appeal_id": ap.id, "authority": authority}, request=request)
    return ap


@transaction.atomic
def decide_appeal(appeal: Appeal, user, request=None, *, status: str, decided_on, decision_summary="", new_compliance_days: int | None = None, media_ids=None):
    _require_role(user, Role.JC, Role.JC_CLERK)
    appeal.status, appeal.decided_on, appeal.decision_summary = status, decided_on, decision_summary
    appeal.save()
    case = appeal.case
    if media_ids:
        attach_media(case, media_ids, user, kind="APPEAL")
    if status in ("DISMISSED", "MODIFIED", "WITHDRAWN") and case.status == S.APPEAL_STAY:
        if new_compliance_days:
            case.compliance_due_at = timezone.now() + timedelta(days=new_compliance_days)
        elif case.compliance_due_at and case.compliance_due_at < timezone.now():
            case.compliance_due_at = timezone.now() + timedelta(days=3)  # residual period, at least statutory minimum
        _set_status(case, S.ORDER_SERVED, user, "APPEAL_DECIDED", request, decision_summary, payload={"appeal_id": appeal.id, "status": status}, owner_role=Role.FIELD_STAFF)
    elif status == "ALLOWED":
        case.closure_reason = f"Order set aside in appeal: {decision_summary}"
        case.closed_at = timezone.now()
        _set_status(case, S.CLOSED, user, "APPEAL_ALLOWED", request, decision_summary, payload={"appeal_id": appeal.id}, owner_role=Role.JC)
    else:
        record_event(case, "APPEAL_UPDATED", actor=user, from_status=case.status, to_status=case.status, remarks=decision_summary, payload={"appeal_id": appeal.id, "status": status}, request=request)
    return appeal


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
    _require_role(user, Role.JE, Role.FIELD_STAFF, Role.AE, Role.JC)
    _require_status(case, S.ORDER_SERVED, S.EXECUTION_DUE, S.ORDER_ISSUED, S.PENDING_JC, S.SCN_SERVED, S.RESPONSE_PENDING_JC, S.NO_RESPONSE)
    if not media_ids:
        raise WorkflowError("Geotagged photographs/videos of the demolition or sealing are mandatory")
    attach_media(case, media_ids, user, kind="EXECUTION" if mode == "CORPORATION" else "COMPLIANCE")
    unverified = case.media.filter(id__in=media_ids, geotag_verified=False, latitude__isnull=False)
    if case.latitude is not None and unverified.exists():
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
    _require_role(user, Role.JC, Role.AE)
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
    _require_role(user, Role.JC)
    _require_status(case, S.CLOSED, S.DROPPED, S.REGULARISED)
    if not remarks:
        raise WorkflowError("Reasons are mandatory to reopen a case")
    case.closed_at = None
    _set_status(case, S.PENDING_JC, user, "REOPEN", request, remarks, owner_role=Role.JC)
    return case


# Transitions exposed to the UI so buttons can be shown per role/status
ACTION_MATRIX = {
    S.DRAFT: {"JE": ["update", "submit_to_ae", "add_media"], "FIELD_STAFF": ["submit_to_ae", "add_media"]},
    S.RETURNED_TO_JE: {"JE": ["update", "submit_to_ae", "add_media"]},
    S.PENDING_AE: {"AE": ["ae_forward", "ae_return", "add_media"], "XEN": ["ae_forward", "ae_return"]},
    S.PENDING_JC: {"JC": ["issue_notice", "issue_order", "drop", "regularise", "add_media"]},
    S.SCN_ISSUED: {"JE": ["record_service", "add_media"], "FIELD_STAFF": ["record_service", "add_media"], "JC": ["issue_notice", "issue_order", "drop"], "JC_CLERK": ["record_response"]},
    S.SCN_SERVED: {"JE": ["record_response", "add_media"], "JC_CLERK": ["record_response", "schedule_hearing"], "JC": ["record_response", "schedule_hearing", "issue_order", "issue_notice", "drop", "regularise"], "AE": ["record_response"]},
    S.RESPONSE_PENDING_AE: {"AE": ["ae_forward_response"], "XEN": ["ae_forward_response"]},
    S.RESPONSE_PENDING_JC: {"JC": ["issue_order", "issue_notice", "schedule_hearing", "drop", "regularise"], "JC_CLERK": ["schedule_hearing", "record_response"]},
    S.RESPONSE_RECEIVED: {"JC": ["issue_order", "schedule_hearing", "drop", "regularise"]},
    S.NO_RESPONSE: {"JC": ["issue_order", "issue_notice", "schedule_hearing", "drop"], "JC_CLERK": ["record_response", "schedule_hearing"], "JE": ["record_response"]},
    S.HEARING_SCHEDULED: {"JC": ["record_hearing", "issue_order", "drop", "regularise"], "JC_CLERK": ["record_hearing", "record_response"]},
    S.ORDER_ISSUED: {"JE": ["record_service", "add_media"], "FIELD_STAFF": ["record_service", "add_media"], "JC": ["record_appeal", "drop"], "JC_CLERK": ["record_appeal"]},
    S.ORDER_SERVED: {"JE": ["record_execution", "add_media"], "FIELD_STAFF": ["record_execution", "add_media"], "JC": ["record_appeal", "record_execution", "drop"], "JC_CLERK": ["record_appeal"]},
    S.APPEAL_STAY: {"JC": ["decide_appeal"], "JC_CLERK": ["decide_appeal"]},
    S.EXECUTION_DUE: {"JE": ["record_execution", "add_media"], "FIELD_STAFF": ["record_execution", "add_media"], "JC": ["record_appeal", "record_execution", "drop"]},
    S.COMPLIED: {"JC": ["close"], "AE": ["close"]},
    S.EXECUTED: {"JC": ["close"], "AE": ["close"]},
    S.CLOSED: {"JC": ["reopen"]},
    S.DROPPED: {"JC": ["reopen"]},
    S.REGULARISED: {"JC": ["reopen"]},
}


def available_actions(case, user) -> list[str]:
    prof = getattr(user, "bvms_profile", None)
    if not prof:
        return []
    role = prof.role
    if role in (Role.ADMIN, Role.COMMISSIONER, Role.ADDL_COMMISSIONER):
        acts = set()
        for r in ACTION_MATRIX.get(case.status, {}).values():
            acts.update(r)
        return sorted(acts)
    return ACTION_MATRIX.get(case.status, {}).get(role, [])
