"""Output serializers: plain functions that turn ORM rows into the JSON shapes the portal and the app
expect (field for field the same as the DRF serializers of the Django edition)."""
from __future__ import annotations

from sqlalchemy import func, inspect
from sqlalchemy.orm import Session

from app.integrations import storage
from app.core.timeutil import now
from app.models import building_violations as m
from app.services.building_violations import access
from app.services.building_violations import hierarchy as H
from app.services.building_violations.location_integrity import explain, summary as integrity_summary


# ---------------------------------------------------------------- helpers
def columns(obj, exclude: tuple = ()) -> dict:
    """Every column of the row (Django's fields="__all__"); foreign keys keep Django's name (zone, not zone_id)."""
    out = {}
    for col in inspect(type(obj)).columns:
        if col.name in exclude:
            continue
        key = col.name[:-3] if (col.foreign_keys and col.name.endswith("_id")) else col.name
        out[key] = getattr(obj, col.name)
    return out


def _abs(request, relpath):
    return storage.absolute_url(request, relpath) if relpath else None


# ---------------------------------------------------------------- masters
def zone(z):
    return {"id": z.id, "code": z.code, "name_en": z.name_en, "name_hi": z.name_hi, "active": z.active}


def division(d):
    return {"id": d.id, "code": d.code, "zone": d.zone_id, "name_en": d.name_en, "active": d.active}


def ward(w):
    return {"id": w.id, "number": w.number, "name_en": w.name_en, "name_hi": w.name_hi, "zone": w.zone_id, "zone_code": w.zone.code if w.zone else None, "division": w.division_id, "active": w.active}


def ward_geo(w):
    return {**ward(w), "boundary": w.boundary}


def legal_section(s):
    return {"id": s.id, "statute": s.statute_id, "statute_title": s.statute.title if s.statute else None, "section": s.section, "heading": s.heading, "kind": s.kind, "text": s.text,
            "schedule_fine_inr": s.schedule_fine_inr, "schedule_daily_fine_inr": s.schedule_daily_fine_inr, "verify": s.verify, "notes": s.notes}


violation_type = columns
order_type = columns
sla_config = columns


def user_lite(u):
    if u is None:
        return None
    p = getattr(u, "bvms_profile", None)
    return {"id": u.id, "username": u.username, "name": p.display_name if p else u.username, "role": p.role if p else None, "role_label": H.role_label(None, p.role) if p else None, "designation": p.designation if p else ""}


def officer_profile(db: Session, p: m.OfficerProfile) -> dict:
    return {
        "id": p.id, "user": user_lite(p.user), "display_name": p.display_name, "role": p.role, "role_label": H.role_label(db, p.role), "designation": p.designation, "employee_code": p.employee_code,
        "mobile": p.mobile, "email": p.email, "zones": [z.id for z in p.zones], "wards": [w.id for w in p.wards], "divisions": [d.id for d in p.divisions],
        "reports_to": p.reports_to_id, "reports_to_name": p.reports_to.display_name if p.reports_to else None, "delegation_order_no": p.delegation_order_no,
        "delegation_order_date": p.delegation_order_date, "parent_profile": p.parent_profile_id, "branch": p.branch_id, "branch_name": p.branch.name_en if p.branch else None,
        "active": p.active, "created_at": p.created_at,
        "permission_overrides": [{"permission": o.permission, "allowed": o.allowed, "reason": o.reason, "order_reference": o.order_reference} for o in p.permission_overrides],
        "effective_permissions": sorted(access.permissions_for(db, p.user)),
    }


def me(db: Session, user) -> dict:
    prof = getattr(user, "bvms_profile", None)
    unread = db.query(func.count(m.Notification.id)).filter(m.Notification.user_id == user.id, m.Notification.read_at.is_(None)).scalar() or 0
    return {
        "id": user.id, "username": user.username, "name": prof.display_name if prof else user.username,
        "role": prof.role if prof else None, "role_label": H.role_label(db, prof.role) if prof else None, "role_label_hi": H.role_label(db, prof.role, "hi") if prof else None,
        "slot": H.slot_of_role(db, prof.role) if prof else None, "can_create_case": bool(prof and prof.active and access.is_action_allowed(db, "*", prof.role, "create")),
        "designation": prof.designation if prof else "", "mobile": prof.mobile if prof else "",
        "zones": [zone(z) for z in prof.zones] if prof else [], "wards": [ward(w) for w in prof.wards] if prof else [],
        "delegation_order_no": prof.delegation_order_no if prof else "",
        "unread_notifications": unread,
        "permissions": sorted(access.permissions_for(db, user)),
        "branch": ({"code": prof.branch.code, "name_en": prof.branch.name_en, "name_hi": prof.branch.name_hi} if prof and prof.branch_id else None),
    }


# ---------------------------------------------------------------- GIS / sanctions
def govt_parcel(p):
    return {"id": p.id, "name": p.name, "agency": p.agency, "land_use": p.land_use, "village": p.village, "khasra_no": p.khasra_no, "area_sqm": p.area_sqm, "ward": p.ward_id,
            "geometry": p.geometry, "bbox": p.bbox, "properties": p.properties, "active": p.active, "created_at": p.created_at}


def land_layer(db: Session, o):
    active_parcels = db.query(func.count(m.GovtLandParcel.id)).filter(m.GovtLandParcel.layer_upload_id == o.id, m.GovtLandParcel.active == True).scalar() or 0  # noqa: E712
    return {"id": o.id, "name": o.name, "layer_key": o.layer_key, "version": o.version, "replaces": o.replaces_id, "agency": o.agency, "source_file": storage.url(o.source_file) if o.source_file else None,
            "file_format": o.file_format, "source": o.source, "survey_date": o.survey_date, "feature_count": o.feature_count, "skipped_count": o.skipped_count,
            "uploaded_by": user_lite(o.uploaded_by), "remarks": o.remarks, "active": o.active, "import_log": o.import_log, "active_parcels": active_parcels, "created_at": o.created_at}


def sanctioned_plan(sp, request=None):
    d = columns(sp)
    d["ward_number"] = sp.ward.number if sp.ward else None
    d["documents"] = [media(x, request) for x in sp.documents]
    return d


# ---------------------------------------------------------------- media
def media(o, request=None):
    c = o.integrity_check
    return {"id": o.id, "case": o.case_id, "notice": o.notice_id, "kind": o.kind, "media_type": o.media_type, "url": _abs(request, o.file), "original_name": o.original_name,
            "size_bytes": o.size_bytes, "sha256": o.sha256, "latitude": o.latitude, "longitude": o.longitude, "accuracy_m": o.accuracy_m, "captured_at": o.captured_at,
            "device_id": o.device_id, "distance_from_case_m": o.distance_from_case_m, "geotag_verified": o.geotag_verified, "integrity_status": o.integrity_status,
            "integrity_reasons": (list(c.reasons) + list(c.flags)) if c else [], "caption": o.caption, "uploaded_by": user_lite(o.uploaded_by), "created_at": o.created_at}


# ---------------------------------------------------------------- case parts
def case_violation(cv):
    return {"id": cv.id, "code": cv.violation_type_id, "violation_type": columns(cv.violation_type), "details": cv.details, "remarks": cv.remarks, "is_primary": cv.is_primary}


def notice_dispatch(d):
    return {"id": d.id, "channel": d.channel, "to": d.to, "status": d.status, "provider_ref": d.provider_ref, "attempts": d.attempts, "last_error": d.last_error, "sent_at": d.sent_at, "created_at": d.created_at}


def notice(n, request=None):
    return {"id": n.id, "case": n.case_id, "case_no": n.case.case_no if n.case else None, "order_type": columns(n.order_type), "notice_no": n.notice_no, "kind": n.kind,
            "issued_by": user_lite(n.issued_by), "issued_at": n.issued_at, "addressee_name": n.addressee_name, "addressee_address": n.addressee_address, "addressee_mobiles": n.addressee_mobiles,
            "response_days": n.response_days, "response_due_at": n.response_due_at, "compliance_days": n.compliance_days, "compliance_due_at": n.compliance_due_at, "hearing_at": n.hearing_at,
            "hearing_venue": n.hearing_venue, "operative_text_en": n.operative_text_en, "operative_text_hi": n.operative_text_hi, "pdf_url": _abs(request, n.pdf), "signed_pdf_url": _abs(request, n.signed_pdf),
            "document_hash": n.document_hash, "verification_code": n.verification_code, "qr_payload": n.qr_payload, "signature_status": n.signature_status, "signer_name": n.signer_name,
            "signer_cert_subject": n.signer_cert_subject, "signed_at": n.signed_at, "signature_error": n.signature_error, "served_at": n.served_at, "served_mode": n.served_mode,
            "served_by": user_lite(n.served_by), "service_remarks": n.service_remarks, "is_final_order": n.is_final_order, "is_legacy": n.is_legacy,
            "dispatches": [notice_dispatch(d) for d in n.dispatches], "delivery_media": [media(x, request) for x in n.media], "created_at": n.created_at}


def case_response(r):
    d = columns(r)
    d["uploaded_by"] = user_lite(r.uploaded_by)
    d["notice_no"] = r.notice.notice_no if r.notice else None
    return d


def hearing(h):
    d = columns(h)
    d["presiding"] = user_lite(h.presiding)
    return d


def appeal(a, request=None):
    d = columns(a)
    d.update({"recorded_by": user_lite(a.recorded_by), "authority_display": a.get_authority_display(), "status_display": a.get_status_display(),
              "stay_order": media(a.stay_order, request) if a.stay_order else None, "final_order": media(a.final_order, request) if a.final_order else None,
              "is_stay_active": a.is_stay_active, "order_no": a.order.notice_no if a.order else None})
    return d


def execution(e):
    d = columns(e)
    d["recorded_by"] = user_lite(e.recorded_by)
    d["verified_by"] = user_lite(e.verified_by)
    return d


def case_event(ev):
    return {"id": ev.id, "at": ev.at, "actor": user_lite(ev.actor), "actor_role": ev.actor_role, "action": ev.action, "from_status": ev.from_status, "to_status": ev.to_status,
            "remarks": ev.remarks, "payload": ev.payload, "latitude": ev.latitude, "longitude": ev.longitude, "hash": ev.hash, "prev_hash": ev.prev_hash}


def notification(n):
    return {"id": n.id, "case": n.case_id, "case_no": n.case.case_no if n.case else None, "title": n.title, "body": n.body, "level": n.level, "read_at": n.read_at, "created_at": n.created_at}


# ---------------------------------------------------------------- the case
def _owner_of(c):
    """The officer on whose desk the case is (by the slot the current owner role fills)."""
    slot = H.slot_of_role(None, c.current_owner_role)
    return {"REPORTER": c.reported_by, "REVIEWER": c.assigned_ae, "AUTHORITY": c.assigned_jc}.get(slot or "")


def people(db: Session, c) -> list[dict]:
    """Stage-by-stage officers of a case, labelled under the current hierarchy (portal 'People' card)."""
    revs = H.reviewers(db, raw=True)
    cur = (c.review_stage or 0) if c.status in ("PENDING_AE", "RESPONSE_PENDING_AE") else 0
    out = [{"slot": "REPORTER", **H.reporter(db).as_dict(), "user": user_lite(c.reported_by)}]
    for i, st in enumerate(revs, 1):
        holder = c.assigned_ae if (len(revs) == 1 or i == cur or (cur == 0 and i == len(revs))) else None
        out.append({"slot": "REVIEWER", **st.as_dict(), "user": user_lite(holder), "current": i == cur})
    out.append({"slot": "AUTHORITY", **H.authority(db).as_dict(), "user": user_lite(c.assigned_jc)})
    return out


def case_list(c, request=None):
    cv = next((x for x in c.violations if x.is_primary), None) or (c.violations[0] if c.violations else None)
    thumb = next((x for x in c.media if x.media_type == "IMAGE"), None)
    return {
        "id": c.id, "case_no": c.case_no, "status": c.status, "status_display": H.case_status_label(None, c), "status_display_hi": H.case_status_label(None, c, "hi"), "priority": c.priority, "source": c.source, "pid": c.pid,
        "address_line": c.address_line, "locality": c.locality, "sector": c.sector, "ward": c.ward_id, "ward_number": c.ward.number if c.ward else None, "zone": c.zone_id,
        "zone_code": c.zone.code if c.zone else None, "latitude": c.latitude, "longitude": c.longitude, "land_type": c.land_type, "owner_name": c.owner_name,
        "construction_stage": c.construction_stage, "reported_by": user_lite(c.reported_by), "assigned_ae": user_lite(c.assigned_ae), "assigned_jc": user_lite(c.assigned_jc),
        "current_owner_role": c.current_owner_role, "current_owner_label": H.role_label(None, c.current_owner_role), "current_owner_slot": H.slot_of_role(None, c.current_owner_role),
        "current_owner": user_lite(_owner_of(c)), "review_stage": c.review_stage, "stage_due_at": c.stage_due_at, "sla_breached": c.sla_breached, "inspected_at": c.inspected_at, "scn_issued_at": c.scn_issued_at,
        "response_due_at": c.response_due_at, "compliance_due_at": c.compliance_due_at, "decision": c.decision, "stop_work_issued": c.stop_work_issued, "sealed": c.sealed,
        "litigation_status": c.litigation_status, "litigation_authority": c.litigation_authority, "stay_until": c.stay_until, "next_hearing_on": c.next_hearing_on,
        "violation_codes": [x.violation_type_id for x in c.violations],
        "primary_violation": {"code": cv.violation_type_id, "title_en": cv.violation_type.title_en, "category": cv.violation_type.category} if cv else None,
        "days_in_stage": (now() - c.status_changed_at).days if c.status_changed_at else 0,
        "thumbnail": _abs(request, thumb.file) if thumb else None,
        "pending_referrals": [r.branch_id for r in c.referrals if r.status == "PENDING"],
        "created_at": c.created_at, "updated_at": c.updated_at, "legacy_reference": c.legacy_reference, "order_issued_at": c.order_issued_at, "order_served_at": c.order_served_at,
        "final_order_no": c.final_order.notice_no if c.final_order else None,
    }


def task_summary(t):
    if not t:
        return None
    cb = t.created_by
    return {"id": t.id, "category": t.get_category_display(), "instructions": t.instructions, "created_by": cb.bvms_profile.display_name if getattr(cb, "bvms_profile", None) else str(cb),
            "batch": t.batch.title if t.batch_id and t.batch else None, "assigned_at": t.assigned_at, "started_at": t.started_at, "start_distance_m": t.start_distance_m}


def case_detail(db: Session, c, request=None, user=None):
    from app.services.building_violations.workflow import available_actions
    H.chain(db)   # warm the hierarchy cache so the labels below follow the admin configuration
    d = case_list(c, request)
    acts = available_actions(db, c, user) if user is not None else []
    codes = set()
    for cv in c.violations:
        codes.update(cv.violation_type.orders_available or [])
    chk = db.query(m.LocationIntegrityCheck).filter(m.LocationIntegrityCheck.case_id == c.id, m.LocationIntegrityCheck.context == "CASE_CREATE").order_by(m.LocationIntegrityCheck.at.desc()).first()
    d.update({
        "complaint_ref": c.complaint_ref, "pid_snapshot": c.pid_snapshot, "pid_linked_mobile": c.pid_linked_mobile, "alternate_mobile": c.alternate_mobile, "village_colony": c.village_colony,
        "pincode": c.pincode, "division": c.division_id, "location_accuracy_m": c.location_accuracy_m, "govt_parcel": govt_parcel(c.govt_parcel) if c.govt_parcel else None,
        "sanctioned_plan": sanctioned_plan(c.sanctioned_plan, request) if c.sanctioned_plan else None, "owner_father_name": c.owner_father_name, "occupier_name": c.occupier_name,
        "builder_name": c.builder_name, "person_on_site": c.person_on_site, "plot_area_sqm": c.plot_area_sqm, "covered_area_sqm": c.covered_area_sqm, "storeys": c.storeys,
        "height_m": c.height_m, "use_observed": c.use_observed, "description": c.description, "measurements": c.measurements, "submitted_at": c.submitted_at,
        "ae_forwarded_at": c.ae_forwarded_at, "jc_received_at": c.jc_received_at, "scn_served_at": c.scn_served_at, "response_received_at": c.response_received_at,
        "hearing_at": c.hearing_at, "decided_at": c.decided_at, "executed_at": c.executed_at, "closed_at": c.closed_at, "decision_reasons": c.decision_reasons,
        "final_order": c.final_order_id, "closure_reason": c.closure_reason, "demolition_cost_inr": c.demolition_cost_inr, "cost_recovery_status": c.cost_recovery_status,
        "violations": [case_violation(x) for x in c.violations], "media": [media(x, request) for x in c.media], "notices": [notice(x, request) for x in c.notices],
        "responses": [case_response(x) for x in c.responses], "hearings": [hearing(x) for x in c.hearings], "appeals": [appeal(x, request) for x in c.appeals],
        "executions": [execution(x) for x in c.executions], "events": [case_event(x) for x in c.events], "referrals": [referral(x) for x in c.referrals],
        "task_summary": task_summary(c.task), "inspector_latitude": c.inspector_latitude, "inspector_longitude": c.inspector_longitude, "inspector_distance_m": c.inspector_distance_m,
        "inspector_integrity": integrity_summary(chk), "available_actions": acts,
        "action_labels": {a: (H.action_label(db, a, "en", case=c) or access.ACTION_LABELS.get(a, a)) for a in acts},
        "action_labels_hi": {a: H.action_label(db, a, "hi", case=c) for a in acts if H.action_label(db, a, "hi", case=c)},
        "people": people(db, c), "current_stage": (H.current_stage(db, c).as_dict() if H.current_stage(db, c) else None),
        "available_order_types": [columns(o) for o in db.query(m.OrderType).filter(m.OrderType.code.in_(codes), m.OrderType.active == True).order_by(m.OrderType.code)] if codes else [],  # noqa: E712
    })
    return d


# ---------------------------------------------------------------- branches, referrals, administration
def branch(b):
    return {"code": b.code, "name_en": b.name_en, "name_hi": b.name_hi, "description": b.description, "head_designation": b.head_designation,
            "default_response_days": b.default_response_days, "active": b.active,
            "officers": [{"user_id": p.user_id, "name": p.display_name, "designation": p.designation} for p in b.officers if p.active]}


def referral(r):
    return {"id": r.id, "case": r.case_id, "case_no": r.case.case_no, "case_status": r.case.status, "case_address": r.case.address_line, "ward_number": r.case.ward.number if r.case.ward else None,
            "branch": branch(r.branch), "referred_by": user_lite(r.referred_by), "referred_at": r.referred_at, "query": r.query, "due_at": r.due_at, "hold_case": r.hold_case, "status": r.status,
            "assigned_to": user_lite(r.assigned_to), "response": r.response, "recommendation": r.recommendation, "responded_by": user_lite(r.responded_by), "responded_at": r.responded_at,
            "closed_by": user_lite(r.closed_by), "closed_at": r.closed_at, "closing_remarks": r.closing_remarks, "is_overdue": bool(r.status == "PENDING" and r.due_at and r.due_at < now()),
            "created_at": r.created_at}


def workflow_rule(r):
    return {"id": r.id, "status": r.status, "role": r.role, "action": r.action, "allowed": r.allowed, "updated_at": r.updated_at}


def workflow_setting(s):
    return {"key": s.key, "value": s.value, "value_type": s.value_type, "label": s.label, "description": s.description, "group": s.group, "choices": s.choices, "updated_at": s.updated_at}


def permission_override(o):
    return {"id": o.id, "permission": o.permission, "allowed": o.allowed, "reason": o.reason, "order_reference": o.order_reference, "updated_at": o.updated_at}


def admin_audit_log(a):
    return {"id": a.id, "at": a.at, "actor": user_lite(a.actor), "action": a.action, "target_type": a.target_type, "target_id": a.target_id, "before": a.before, "after": a.after,
            "order_reference": a.order_reference, "remarks": a.remarks, "ip_address": a.ip_address}


# ---------------------------------------------------------------- planned inspections
def inspection_task(db: Session, t, request=None):
    chk = db.query(m.LocationIntegrityCheck).filter(m.LocationIntegrityCheck.task_id == t.id, m.LocationIntegrityCheck.context == "TASK_START").order_by(m.LocationIntegrityCheck.at.desc()).first()
    c = t.case
    return {"start_integrity": integrity_summary(chk), "id": t.id, "batch": t.batch_id, "batch_title": t.batch.title if t.batch else None, "category": t.category, "category_display": t.get_category_display(),
            "pid": t.pid, "pid_snapshot": t.pid_snapshot, "address": t.address, "owner_name": t.owner_name, "owner_mobile": t.owner_mobile, "latitude": t.latitude, "longitude": t.longitude,
            "ward": t.ward_id, "ward_number": t.ward.number if t.ward else None, "zone": t.zone_id, "zone_code": t.zone.code if t.zone else None, "instructions": t.instructions, "priority": t.priority,
            "created_by": user_lite(t.created_by), "assigned_to": user_lite(t.assigned_to), "assigned_at": t.assigned_at, "due_at": t.due_at, "status": t.status, "status_display": t.get_status_display(),
            "related_case": t.related_case_id, "related_case_no": t.related_case.case_no if t.related_case else None, "started_at": t.started_at, "start_latitude": t.start_latitude,
            "start_longitude": t.start_longitude, "start_distance_m": t.start_distance_m, "completed_at": t.completed_at, "outcome_remarks": t.outcome_remarks, "geofence_m": t.geofence_m,
            "case_no": c.case_no if c else None, "case_id": c.id if c else None, "case_status": c.status if c else None,
            "is_overdue": bool(t.status in ("ASSIGNED", "UNASSIGNED", "IN_PROGRESS") and t.due_at and t.due_at < now()),
            "media": [media(x, request) for x in t.media], "created_at": t.created_at, "updated_at": t.updated_at}


def inspection_batch(db: Session, b):
    progress = {st: n for st, n in db.query(m.InspectionTask.status, func.count(m.InspectionTask.id)).filter(m.InspectionTask.batch_id == b.id).group_by(m.InspectionTask.status)}
    return {"id": b.id, "title": b.title, "category": b.category, "created_by": user_lite(b.created_by), "instructions": b.instructions, "due_at": b.due_at, "total": b.total,
            "errors": b.errors, "progress": progress, "created_at": b.created_at}


def integrity_check(o):
    d = columns(o, exclude=("signals", "ip_intel", "attestation_detail"))
    d.update({"officer": user_lite(o.officer), "context_display": o.get_context_display(), "case_no": o.case.case_no if o.case else None, "explanation": explain(list(o.reasons) + list(o.flags))})
    return d


def legacy_batch(b):
    return {"id": b.id, "title": b.title, "created_by": user_lite(b.created_by), "created_at": b.created_at, "total_rows": b.total_rows, "imported": b.imported, "errors": b.errors}
