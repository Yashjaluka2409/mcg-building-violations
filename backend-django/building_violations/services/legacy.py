"""Orders issued before this system existed ("legacy" demolition / sealing / eviction orders).

MCG has a backlog of paper orders - demolition orders under s.261, sealing orders under s.263A, eviction orders
under s.408A and so on - whose service, appeals and execution still have to be tracked. This module lets the
JC office (permission LEGACY_ORDERS_MANAGE) bring them into the system, one at a time or from a register
(CSV / XLSX), and then keep their status current with the same case machinery as new cases:

* a ``ViolationCase`` is created with ``source = "LEGACY_ORDER"`` at the stage the paper file is actually in
  (order issued / served / execution due / stayed / complied / executed / closed / regularised / dropped);
* the original order becomes a ``Notice`` with ``is_legacy = True`` - the original number, date and signatory
  are kept, nothing is re-signed or re-generated, and the scanned copy is attached as media
  (kind LEGACY_ORDER). It still gets a verification code so the public verify page can say "order on record";
* every historical date is written into the case (order_issued_at, order_served_at, compliance_due_at,
  executed_at, closed_at), an ExecutionRecord / Appeal is created where applicable, and the hash-chained event
  log records a LEGACY_IMPORT event with the raw register row followed by the status it was set to;
* from then on the normal actions apply (record delivery, appeal / stay, execution with geotagged evidence,
  verify & close, reopen). ``update_status()`` additionally lets the JC office record historical status changes
  from the paper file - service, execution, stay, closure - without the field-evidence rules, because that
  evidence never existed digitally. Each such update is an audited event with the authorising reference.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..models import (Appeal, CaseStatus as S, CaseViolation, ExecutionRecord, LegacyOrderBatch, MediaAttachment, Notice, OrderType, Role,
                      ViolationCase, ViolationType, Ward)
from . import access
from .audit import record_event
from .geo import ward_for_point
from .numbering import next_case_no, verification_code
from .workflow import WorkflowError, _set_status, attach_media

LEGACY_SOURCE = "LEGACY_ORDER"
ALLOWED_STATUSES = (S.ORDER_ISSUED, S.ORDER_SERVED, S.EXECUTION_DUE, S.APPEAL_STAY, S.COMPLIED, S.EXECUTED, S.CLOSED, S.REGULARISED, S.DROPPED)
DECISION_BY_ORDER = {"DEMOLITION_ORDER_261": "DEMOLITION", "EVICTION_DEMOLITION_ORDER_408A": "EVICTION", "DEMOLITION_ORDER_284": "DEMOLITION",
                     "SEALING_263A": "SEALING", "DANGEROUS_BUILDING_ORDER_265": "DEMOLITION", "VACATE_ORDER_266": "VACATE", "OC_REVOCATION_HBC_4_12": "OC_REVOKED"}
OWNER_ROLE = {S.ORDER_ISSUED: Role.JE, S.ORDER_SERVED: Role.JE, S.EXECUTION_DUE: Role.FIELD_STAFF, S.APPEAL_STAY: Role.JC,
              S.COMPLIED: Role.JC, S.EXECUTED: Role.JC, S.CLOSED: Role.JC, S.REGULARISED: Role.JC, S.DROPPED: Role.JC}

TEMPLATE_COLUMNS = ["order_no", "order_date", "order_type", "issued_by", "pid", "address", "locality", "sector", "ward_number", "owner_name", "owner_mobile",
                    "violation_codes", "description", "compliance_days", "served_on", "served_mode", "current_status", "executed_on", "execution_action",
                    "execution_mode", "cost_incurred_inr", "appeal_authority", "appeal_no", "appeal_filed_on", "stay_until", "closed_on", "legacy_reference", "remarks"]
TEMPLATE_EXAMPLE = ["MCG/JC-2/DEMO/2023/0412", "2023-08-14", "DEMOLITION_ORDER_261", "Sh. R. K. Sharma, Joint Commissioner, Zone 2", "GGN012345",
                    "H.No. 123, Sector 14", "Sector 14", "14", "19", "Ramesh Kumar", "9811100001", "UC_WITHOUT_SANCTION;COVERAGE_EXCESS",
                    "Third floor raised without sanction", "15", "2023-08-20", "AFFIXATION", "", "", "", "", "", "", "", "", "", "",
                    "Demolition order register 2023-24, page 61", ""]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _dt(d, hour=10):
    """Historical dates come as dates; store them as aware datetimes at 10:00 local time."""
    if d is None or d == "":
        return None
    if isinstance(d, datetime):
        return d if timezone.is_aware(d) else timezone.make_aware(d)
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return timezone.make_aware(datetime.combine(d, time(hour, 0)))


def _authorize(user):
    prof = getattr(user, "bvms_profile", None)
    if not prof:
        raise WorkflowError("No officer profile", 403)
    if prof.role in access.MANAGEMENT_ROLES or access.has_perm(user, "LEGACY_ORDERS_MANAGE"):
        return prof
    raise WorkflowError("Only the JC office / module administrator may record orders issued outside the system", 403)


def _ward(d):
    w = d.get("ward")
    if w is not None and hasattr(w, "pk"):
        return w
    if w:
        return Ward.objects.filter(pk=w).first()
    if d.get("ward_number"):
        return Ward.objects.filter(number=int(d["ward_number"])).first()
    if d.get("latitude") and d.get("longitude"):
        return ward_for_point(d["latitude"], d["longitude"])
    return None


def derive_status(d) -> str:
    if d.get("current_status"):
        st = d["current_status"]
        if st not in ALLOWED_STATUSES:
            raise WorkflowError(f"current_status must be one of {', '.join(ALLOWED_STATUSES)}")
        return st
    if d.get("closed_on"):
        return S.CLOSED
    if d.get("executed_on"):
        return S.COMPLIED if d.get("execution_mode") == ExecutionRecord.Mode.OWNER_SELF else S.EXECUTED
    if d.get("stay_granted") or d.get("stay_until"):
        return S.APPEAL_STAY
    if d.get("served_on"):
        due = d.get("_compliance_due_at")
        return S.EXECUTION_DUE if due and due < timezone.now() else S.ORDER_SERVED
    return S.ORDER_ISSUED


# ---------------------------------------------------------------------------
# single order
# ---------------------------------------------------------------------------
@transaction.atomic
def import_order(user, d: dict, request=None, batch: LegacyOrderBatch | None = None) -> ViolationCase:
    prof = _authorize(user)
    order_no = str(d.get("order_no") or "").strip()
    if not order_no:
        raise WorkflowError("The original order number is required")
    if Notice.objects.filter(notice_no=order_no).exists():
        raise WorkflowError(f"Order {order_no} is already on record")
    if not d.get("order_date"):
        raise WorkflowError("The date of the order is required")
    if not (d.get("pid") or d.get("address_line")):
        raise WorkflowError("PID or address of the property is required")
    ot = OrderType.objects.filter(code=d.get("order_type") or "DEMOLITION_ORDER_261", active=True).first()
    if not ot or ot.kind != "ORDER":
        raise WorkflowError(f"Unknown order type {d.get('order_type')!r}; use one of the final-order codes (e.g. DEMOLITION_ORDER_261, SEALING_263A)")

    ward = _ward(d)
    zone = ward.zone if ward else None
    order_at = _dt(d["order_date"])
    served_at = _dt(d.get("served_on"))
    days = int(d["compliance_days"]) if d.get("compliance_days") not in (None, "") else ot.default_days
    if d.get("compliance_due_on"):
        due_at = _dt(d["compliance_due_on"], 23)
    elif days:
        due_at = (served_at or order_at) + timedelta(days=days)
    else:
        due_at = None
    d["_compliance_due_at"] = due_at
    status = derive_status(d)

    case = ViolationCase(
        case_no=next_case_no(zone.code if zone else None), status=S.DRAFT, source=LEGACY_SOURCE, legacy_reference=str(d.get("legacy_reference") or "")[:120],
        legacy_batch=batch, pid=str(d.get("pid") or "")[:40], pid_linked_mobile=str(d.get("pid_linked_mobile") or d.get("owner_mobile") or "")[:15],
        alternate_mobile=str(d.get("alternate_mobile") or "")[:15], address_line=str(d.get("address_line") or d.get("address") or ""),
        locality=str(d.get("locality") or ""), sector=str(d.get("sector") or ""), village_colony=str(d.get("village_colony") or ""),
        pincode=str(d.get("pincode") or ""), latitude=d.get("latitude") or None, longitude=d.get("longitude") or None, ward=ward, zone=zone,
        division=ward.division if ward else None, land_type=d.get("land_type") or "UNKNOWN", owner_name=str(d.get("owner_name") or ""),
        owner_father_name=str(d.get("owner_father_name") or ""), occupier_name=str(d.get("occupier_name") or ""),
        description=str(d.get("description") or f"Imported from register: {ot.title_en} No. {order_no} dated {d['order_date']}"),
        reported_by=user, assigned_jc=user if prof.role == Role.JC else (prof.parent_profile.user if prof.role == Role.JC_CLERK and prof.parent_profile else None),
        current_owner_role=OWNER_ROLE.get(status, Role.JC), inspected_at=_dt(d.get("scn_date")) or order_at, jc_received_at=order_at,
        scn_issued_at=_dt(d.get("scn_date")), decided_at=order_at, decision=DECISION_BY_ORDER.get(ot.code, ot.code),
        decision_reasons=str(d.get("remarks") or ""), order_issued_at=order_at, order_served_at=served_at, compliance_due_at=due_at,
        sealed=ot.code in ("SEALING_263A", "RESEALING_263A"), priority=d.get("priority") or "NORMAL",
    )
    case.save()

    codes = d.get("violations") or []
    for i, v in enumerate(codes):
        code = v["code"] if isinstance(v, dict) else str(v)
        vt = ViolationType.objects.filter(code=code).first()
        if not vt:
            raise WorkflowError(f"Unknown violation code {code}")
        CaseViolation.objects.create(case=case, violation_type=vt, remarks=(v.get("remarks", "") if isinstance(v, dict) else ""),
                                     details=(v.get("details", {}) if isinstance(v, dict) else {}), is_primary=(i == 0))

    signer = ", ".join(x for x in (str(d.get("issued_by_name") or ""), str(d.get("issued_by_designation") or "")) if x)
    n = Notice.objects.create(
        case=case, order_type=ot, notice_no=order_no, kind=ot.kind, issued_by=user, issued_at=order_at, addressee_name=case.owner_name or "Owner / occupier",
        addressee_address=case.address_line, addressee_mobiles=[m for m in (case.pid_linked_mobile, case.alternate_mobile) if m],
        compliance_days=days or 0, compliance_due_at=due_at, operative_text_en=str(d.get("remarks") or ""), is_final_order=True, is_legacy=True,
        signature_status=Notice.SignatureStatus.UNSIGNED, signer_name=signer, verification_code=verification_code(),
        context_snapshot={"legacy": {k: (str(v) if isinstance(v, (date, datetime, Decimal)) else v) for k, v in d.items() if not k.startswith("_") and k != "media_ids"}},
        served_at=served_at, served_mode=(d.get("served_mode") or "") if served_at else "", service_remarks="Service recorded from the paper file" if served_at else "",
    )
    case.final_order = n
    case.save(update_fields=["final_order"])

    if d.get("media_ids"):
        attach_media(case, d["media_ids"], user, kind="LEGACY_ORDER", notice=n)

    record_event(case, "LEGACY_IMPORT", actor=user, from_status="", to_status=S.DRAFT, request=request,
                 remarks=f"Order {order_no} of {d['order_date']} imported from the paper record" + (f" ({d.get('legacy_reference')})" if d.get("legacy_reference") else ""),
                 payload={"order_no": order_no, "order_type": ot.code, "order_date": str(d["order_date"]), "signatory": signer,
                          "order_reference": str(d.get("order_reference") or ""), "batch": batch.id if batch else None})
    _apply_history(case, n, user, d, status, request)
    return case


def _apply_history(case, n, user, d, status, request, remarks=""):
    """Write the historical facts behind ``status`` (execution / appeal / closure) and set the status."""
    payload = {"status": status}
    if d.get("executed_on") or status in (S.EXECUTED, S.COMPLIED):
        ex_on = _dt(d.get("executed_on")) or timezone.now()
        mode = d.get("execution_mode") or (ExecutionRecord.Mode.OWNER_SELF if status == S.COMPLIED else ExecutionRecord.Mode.CORPORATION)
        action = d.get("execution_action") or ("SEALING" if case.decision == "SEALING" else "EVICTION" if case.decision == "EVICTION" else "DEMOLITION")
        ex = ExecutionRecord.objects.create(case=case, order=n, action=action, mode=mode, executed_on=ex_on, cost_incurred_inr=d.get("cost_incurred_inr") or None,
                                            area_demolished_sqm=d.get("area_demolished_sqm") or None, remarks=str(d.get("execution_remarks") or remarks or "Recorded from the paper file"),
                                            recorded_by=user)
        case.executed_at = ex_on
        if action == "SEALING":
            case.sealed = True
        if d.get("cost_incurred_inr"):
            case.demolition_cost_inr, case.cost_recovery_status = d["cost_incurred_inr"], d.get("cost_recovery_status") or "PENDING"
        if d.get("media_ids") and status in (S.EXECUTED, S.COMPLIED) and case.status != S.DRAFT:
            attach_media(case, d["media_ids"], user, kind="EXECUTION" if mode == "CORPORATION" else "COMPLIANCE")
        payload.update({"execution_id": ex.id, "action": action, "mode": mode, "executed_on": str(ex_on.date())})
    if d.get("appeal_authority"):
        stay = bool(d.get("stay_granted")) or bool(d.get("stay_until")) or status == S.APPEAL_STAY
        ap = Appeal.objects.create(case=case, order=n, authority=d["appeal_authority"], authority_other=str(d.get("authority_other") or ""),
                                   filed_on=d.get("appeal_filed_on") or d.get("stay_order_date") or timezone.localdate(), appeal_no=str(d.get("appeal_no") or ""),
                                   appellant_name=str(d.get("appellant_name") or case.owner_name), status=Appeal.Status.STAYED if stay else Appeal.Status.PENDING,
                                   stay_granted=stay, stay_order_date=d.get("stay_order_date") or None, stay_until=d.get("stay_until") or None, recorded_by=user)
        case.litigation_status = "STAYED" if stay else "APPEAL_PENDING"
        case.litigation_authority = d["appeal_authority"]
        case.stay_until = d.get("stay_until") or None
        payload.update({"appeal_id": ap.id, "authority": ap.authority, "stay": stay})
    if status in (S.CLOSED, S.REGULARISED, S.DROPPED):
        case.closed_at = _dt(d.get("closed_on"), 17) or timezone.now()
        case.closure_reason = str(d.get("closure_reason") or d.get("remarks") or "Closed as per the paper record")
        payload["closed_on"] = str(case.closed_at.date())
    if status == S.ORDER_SERVED or status == S.EXECUTION_DUE:
        payload.update({"served_on": str(case.order_served_at.date()) if case.order_served_at else None,
                        "compliance_due": str(case.compliance_due_at.date()) if case.compliance_due_at else None})
    case.save()
    _set_status(case, status, user, "LEGACY_STATUS", request, remarks or "Status as per the paper record at the time of import", payload=payload,
                owner_role=OWNER_ROLE.get(status, Role.JC))


# ---------------------------------------------------------------------------
# status updates from the paper file
# ---------------------------------------------------------------------------
@transaction.atomic
def update_status(case: ViolationCase, user, d: dict, request=None) -> ViolationCase:
    """Record a historical status change of an imported order (no field-evidence rules; audited)."""
    _authorize(user)
    if case.source != LEGACY_SOURCE:
        raise WorkflowError("Only orders imported from the paper record can be updated this way; use the normal case actions", 400)
    status = d["status"]
    if status not in ALLOWED_STATUSES:
        raise WorkflowError(f"status must be one of {', '.join(ALLOWED_STATUSES)}")
    on = d.get("on_date") or timezone.localdate()
    n = case.final_order
    remarks = str(d.get("remarks") or "")
    if d.get("order_reference"):
        remarks = (remarks + f" [ref: {d['order_reference']}]").strip()
    if status in (S.ORDER_SERVED, S.EXECUTION_DUE):
        served_at = _dt(on)
        case.order_served_at = case.order_served_at or served_at
        if n and not n.served_at:
            n.served_at, n.served_mode, n.served_by, n.service_remarks = served_at, d.get("served_mode") or "", user, remarks or "Service recorded from the paper file"
            if n.compliance_days:
                n.compliance_due_at = served_at + timedelta(days=n.compliance_days)
                case.compliance_due_at = n.compliance_due_at
            n.save()
        if d.get("media_ids"):
            attach_media(case, d["media_ids"], user, kind="ORDER_DELIVERY", notice=n)
    if status == S.APPEAL_STAY and not d.get("appeal_authority"):
        raise WorkflowError("Name the appellate authority / court that granted the stay")
    if status == S.APPEAL_STAY and d.get("media_ids"):
        attach_media(case, d["media_ids"], user, kind="STAY_ORDER")
    if status in (S.EXECUTED, S.COMPLIED):
        d.setdefault("executed_on", on)
    if status in (S.CLOSED, S.REGULARISED, S.DROPPED):
        d.setdefault("closed_on", on)
    if status in (S.ORDER_SERVED, S.ORDER_ISSUED) and case.litigation_status == "STAYED":
        # stay vacated: close the open appeal
        case.appeals.filter(status=Appeal.Status.STAYED).update(status=Appeal.Status.STAY_VACATED, stay_granted=False)
        case.litigation_status, case.stay_until = "DECIDED", None
    _apply_history(case, n, user, d, status, request, remarks=remarks)
    return case


# ---------------------------------------------------------------------------
# bulk import from a register
# ---------------------------------------------------------------------------
def row_to_data(r: dict) -> dict:
    g = lambda k: (str(r.get(k)).strip() if r.get(k) is not None else "")
    codes = [c.strip() for c in g("violation_codes").replace(",", ";").split(";") if c.strip()]
    d = {"order_no": g("order_no"), "order_date": g("order_date"), "order_type": g("order_type") or "DEMOLITION_ORDER_261", "issued_by_name": g("issued_by"),
         "pid": g("pid"), "address_line": g("address"), "locality": g("locality"), "sector": g("sector"), "ward_number": g("ward_number") or None,
         "owner_name": g("owner_name"), "owner_mobile": g("owner_mobile"), "violations": [{"code": c} for c in codes], "description": g("description"),
         "compliance_days": g("compliance_days") or None, "served_on": g("served_on") or None, "served_mode": g("served_mode"), "current_status": g("current_status"),
         "executed_on": g("executed_on") or None, "execution_action": g("execution_action"), "execution_mode": g("execution_mode"),
         "cost_incurred_inr": g("cost_incurred_inr") or None, "appeal_authority": g("appeal_authority"), "appeal_no": g("appeal_no"),
         "appeal_filed_on": g("appeal_filed_on") or None, "stay_until": g("stay_until") or None, "stay_granted": bool(g("stay_until")),
         "closed_on": g("closed_on") or None, "legacy_reference": g("legacy_reference"), "remarks": g("remarks")}
    for k in ("appeal_filed_on", "stay_until"):
        if d[k]:
            d[k] = date.fromisoformat(d[k][:10])
    if d["cost_incurred_inr"]:
        d["cost_incurred_inr"] = Decimal(d["cost_incurred_inr"])
    return d


def import_rows(user, rows: list[dict], *, title: str, source_file=None, request=None, order_reference: str = "") -> LegacyOrderBatch:
    _authorize(user)
    batch = LegacyOrderBatch.objects.create(title=title or f"Legacy orders {timezone.localdate()}", created_by=user, source_file=source_file, total_rows=len(rows))
    errors, n = [], 0
    for i, r in enumerate(rows, start=2):
        try:
            d = row_to_data(r)
            d["order_reference"] = order_reference
            import_order(user, d, request=request, batch=batch)
            n += 1
        except WorkflowError as e:
            errors.append({"row": i, "order_no": str(r.get("order_no") or ""), "error": str(e)})
        except Exception as e:  # bad dates, decimals ...
            errors.append({"row": i, "order_no": str(r.get("order_no") or ""), "error": f"{type(e).__name__}: {e}"[:300]})
    batch.imported, batch.errors = n, errors
    batch.save(update_fields=["imported", "errors"])
    access.log_admin(user, "LEGACY_IMPORT", "LegacyOrderBatch", batch.id, after={"imported": n, "errors": len(errors)}, order_reference=order_reference,
                     remarks=title, request=request)
    return batch


def summary(qs) -> dict:
    from django.db.models import Count
    base = qs.filter(source=LEGACY_SOURCE)
    by_status = {r["status"]: r["c"] for r in base.values("status").annotate(c=Count("id"))}
    open_states = (S.ORDER_ISSUED, S.ORDER_SERVED, S.EXECUTION_DUE, S.APPEAL_STAY)
    return {"total": base.count(), "open": sum(by_status.get(s, 0) for s in open_states), "by_status": by_status,
            "execution_due": by_status.get(S.EXECUTION_DUE, 0), "stayed": by_status.get(S.APPEAL_STAY, 0),
            "batches": LegacyOrderBatch.objects.count()}
