"""Notice register, PDF download, SMS re-send, re-signing, and the public QR verification page."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from app.routers.building_violations._router import SyncRouter
from sqlalchemy import select

from app.integrations import storage
from app.models import building_violations as m
from app.db.util import to_uuid
from app.services.building_violations import access
from app.services.building_violations.notices import dispatch_sms, render_and_sign
from app.schemas.building_violations import inputs as s
from app.schemas.building_violations import outputs as ser
from app.core.http import apply_filters, apply_ordering, apply_search, paginate, resp
from app.routers.building_violations.deps import DB, Officer, check_perm
from app.repositories.building_violations import case_criteria

router = SyncRouter(prefix="/notices")
public = SyncRouter()


def scoped(db, user):
    q = db.query(m.Notice).join(m.ViolationCase, m.Notice.case_id == m.ViolationCase.id)
    if access.has_perm(db, user, "NOTICE_VIEW_ALL") or user.bvms_profile.role in access.MANAGEMENT_ROLES:
        return q
    return q.filter(*case_criteria(db, user))


def get_notice(db, user, pk) -> m.Notice:
    u = to_uuid(pk)
    n = scoped(db, user).filter(m.Notice.id == u).first() if u else None
    if not n:
        raise HTTPException(404, "Not found.")
    return n


@router.get("/")
def list_notices(request: Request, user: Officer, db: DB):
    p = request.query_params
    q = apply_filters(scoped(db, user), m.Notice, p, ("case", "order_type", "kind", "signature_status", "served_mode", "is_final_order"))
    q = apply_search(q, p, [m.Notice.notice_no, m.ViolationCase.case_no, m.Notice.addressee_name, m.ViolationCase.pid])
    q = apply_ordering(q, p, {k: getattr(m.Notice, k) for k in ("issued_at", "served_at", "response_due_at", "compliance_due_at")}, [m.Notice.issued_at.desc()])
    return resp(paginate(request, q, lambda n: ser.notice(n, request)))


@router.get("/{pk}/")
def notice_detail(pk: str, request: Request, user: Officer, db: DB):
    return resp(ser.notice(get_notice(db, user, pk), request))


@router.get("/{pk}/pdf/")
def notice_pdf(pk: str, user: Officer, db: DB):
    n = get_notice(db, user, pk)
    rel = n.signed_pdf or n.pdf
    if not rel or not storage.exists(rel):
        raise HTTPException(404, "Not found.")
    return storage.file_response(rel, "application/pdf", f'{n.notice_no.replace("/", "-")}.pdf')


@router.post("/{pk}/resend_sms/")
def resend_sms(pk: str, body: s.ResendSmsIn, user: Officer, db: DB):
    check_perm(db, user, "NOTICE_RESEND_SMS")
    n = get_notice(db, user, pk)
    mobiles = list(n.addressee_mobiles or [])
    for mm in body.mobiles:
        if mm not in mobiles:
            mobiles.append(mm)
    n.addressee_mobiles = mobiles
    db.flush()
    return resp({"dispatches": [{"to": d.to, "status": d.status} for d in dispatch_sms(db, n)]})


@router.post("/{pk}/resign/")
def resign(pk: str, request: Request, user: Officer, db: DB):
    """Re-run signing (e.g. after the DSC/eSign backend was configured)."""
    check_perm(db, user, "NOTICE_RESIGN")
    n = render_and_sign(db, get_notice(db, user, pk))
    return resp(ser.notice(n, request))


@public.get("/public/verify/{code}/")
def public_verify(code: str, request: Request, db: DB):
    """Public page behind the QR code: confirms that a notice number/verification code is genuine and
    shows its status. No personal data beyond what is printed on the notice."""
    n = db.query(m.Notice).filter(m.Notice.verification_code == code.upper()).first()
    if not n:
        return resp({"valid": False, "detail": "No notice found for this verification code"}, 404)
    h = request.query_params.get("h")
    hash_ok = (n.document_hash.startswith(h) if h else None)
    prof = getattr(n.issued_by, "bvms_profile", None)
    return resp({
        "valid": True, "hash_match": hash_ok, "notice_no": n.notice_no, "kind": n.kind, "order_type": n.order_type.title_en, "statute": n.order_type.statute,
        "section": n.order_type.section, "issued_at": n.issued_at, "issued_by": (prof.display_name if prof else ""), "designation": (prof.designation if prof else ""),
        "case_no": n.case.case_no, "property": {"pid": n.case.pid, "address": n.case.address_line, "ward": n.case.ward.number if n.case.ward else None},
        "addressee": n.addressee_name, "response_due_at": n.response_due_at, "compliance_due_at": n.compliance_due_at, "served_at": n.served_at,
        "signature_status": n.signature_status, "signer": n.signer_name, "document_hash": n.document_hash, "case_status": n.case.get_status_display(),
        "superseded": bool(n.superseded_by_id),
    })
