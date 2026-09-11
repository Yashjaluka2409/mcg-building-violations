"""Issue a notice/order: number it, render, hash, sign, store, dispatch SMS."""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.integrations import storage
from app.core.config import settings
from app.core.timeutil import make_aware_local, now
from app.models.building_violations import Notice, NoticeDispatch, OrderType, SignatureStatus, ViolationCase
from app.integrations import whatsapp
from app.integrations.sms import get_gateway, normalise_mobile, order_message, scn_message
from app.services.building_violations.numbering import next_notice_no, verification_code
from app.services.building_violations.pdf import html_to_pdf, render_notice_html, sha256_hex
from app.services.building_violations.signing import get_signer

log = logging.getLogger(__name__)

ORDER_KINDS_FINAL = {"DEMOLITION_ORDER_261", "EVICTION_DEMOLITION_ORDER_408A", "DEMOLITION_ORDER_284",
                     "DANGEROUS_BUILDING_ORDER_265", "VACATE_ORDER_266", "OC_REVOCATION_HBC_4_12"}
SCN_TYPES = {"SCN_261", "SCN_408A", "SCN_284", "SCN_256_CANCELLATION", "ALTERATION_NOTICE_263",
             "REMOVAL_NOTICE_235", "MISUSE_NOTICE_265", "OC_NOTICE_264"}


def build_notice(db: Session, case: ViolationCase, order_type: OrderType, issued_by, *, addressee_name: str, addressee_address: str,
                 mobiles: list[str], response_days: int = 0, compliance_days: int = 0, hearing_at=None,
                 hearing_venue: str = "", operative_text_en: str = "", operative_text_hi: str = "",
                 is_final_order: bool = False, extra_context: dict | None = None) -> Notice:
    t = now()
    if order_type.min_days and (response_days or compliance_days):
        if order_type.kind == "NOTICE" and response_days < order_type.min_days:
            raise ValueError(f"Statutory minimum for {order_type.code} is {order_type.min_days} days")
        if order_type.kind == "ORDER" and compliance_days < order_type.min_days:
            raise ValueError(f"Statutory minimum for {order_type.code} is {order_type.min_days} days")
    mobiles = [m for m in (normalise_mobile(x) for x in mobiles) if m]
    n = Notice(
        case=case, order_type=order_type, notice_no=next_notice_no(db, order_type.code), kind=order_type.kind,
        issued_by=issued_by, issued_at=t, addressee_name=addressee_name or case.owner_name or "The Owner/Occupier",
        addressee_address=addressee_address or case.address_line, addressee_mobiles=mobiles,
        response_days=response_days, response_due_at=(t + timedelta(days=response_days)) if response_days else None,
        compliance_days=compliance_days, compliance_due_at=(t + timedelta(days=compliance_days)) if compliance_days else None,
        hearing_at=make_aware_local(hearing_at) if hearing_at else None, hearing_venue=hearing_venue or "",
        operative_text_en=operative_text_en or order_type.body_override_en, operative_text_hi=operative_text_hi or order_type.body_override_hi,
        verification_code=verification_code(), is_final_order=is_final_order,
    )
    n.qr_payload = f"{settings.PUBLIC_VERIFY_BASE.rstrip('/')}/{n.verification_code}"
    db.add(n)
    db.flush()
    render_and_sign(db, n, extra_context=extra_context)
    return n


def render_and_sign(db: Session, notice: Notice, extra_context: dict | None = None) -> Notice:
    html = render_notice_html(db, notice, extra_context)
    notice.html_snapshot = html
    pdf_bytes = html_to_pdf(html)
    notice.document_hash = sha256_hex(pdf_bytes)
    notice.qr_payload = f"{settings.PUBLIC_VERIFY_BASE.rstrip('/')}/{notice.verification_code}?h={notice.document_hash[:16]}"
    # re-render once so the QR embeds the hash prefix as well
    html = render_notice_html(db, notice, extra_context)
    notice.html_snapshot = html
    pdf_bytes = html_to_pdf(html)
    notice.document_hash = sha256_hex(pdf_bytes)
    fname = notice.notice_no.replace("/", "-")
    notice.pdf = storage.save_bytes(storage.notice_pdf_path(f"{fname}.pdf"), pdf_bytes)
    signer = get_signer()
    issuer = getattr(notice.issued_by, "bvms_profile", None)
    signer_name = issuer.display_name if issuer else str(notice.issued_by)
    res = signer.sign(pdf_bytes, reason=f"{notice.order_type.code} {notice.notice_no}", signer_name=signer_name)
    if res.ok and res.pdf:
        notice.signed_pdf = storage.save_bytes(storage.notice_pdf_path(f"{fname}-signed.pdf"), res.pdf)
        notice.signature_status = SignatureStatus.SIGNED
        notice.signer_name, notice.signer_cert_subject, notice.signer_cert_serial = res.signer_name, res.subject[:300], res.serial[:120]
        notice.signed_at = now()
        notice.signature_error = ""
    else:
        notice.signature_status = SignatureStatus.FAILED
        notice.signature_error = res.error[:2000]
    db.flush()
    return notice


def dispatch_sms(db: Session, notice: Notice) -> list[NoticeDispatch]:
    gw = get_gateway()
    cfg = settings.sms
    is_scn = notice.order_type.code in SCN_TYPES
    msg = scn_message(notice) if is_scn else order_message(notice)
    template = cfg.get("DLT_TEMPLATE_SCN") if is_scn else cfg.get("DLT_TEMPLATE_ORDER")
    out = []
    for to in notice.addressee_mobiles:
        d = NoticeDispatch(notice=notice, channel="SMS", to=to, message=msg)
        res = gw.send(to, msg, template or "")
        d.attempts = 1
        d.status = "SENT" if res.ok else "FAILED"
        d.provider_ref, d.last_error = res.provider_ref[:120], res.error[:2000]
        d.sent_at = now() if res.ok else None
        db.add(d)
        out.append(d)
        if whatsapp.enabled() and whatsapp.campaign_for(is_scn):
            ok, ref, err = whatsapp.send_template(to, whatsapp.campaign_for(is_scn), notice.addressee_name, whatsapp.notice_params(notice, is_scn))
            w = NoticeDispatch(notice=notice, channel="WHATSAPP", to=to, message=msg, attempts=1, status="SENT" if ok else "FAILED", provider_ref=ref[:120], last_error=err[:2000], sent_at=now() if ok else None)
            db.add(w)
            out.append(w)
    db.flush()
    return out


def retry_dispatch(db: Session, d: NoticeDispatch):
    gw = get_gateway()
    res = gw.send(d.to, d.message, "")
    d.attempts += 1
    d.status = "SENT" if res.ok else "FAILED"
    d.provider_ref, d.last_error = res.provider_ref[:120], res.error[:2000]
    d.sent_at = now() if res.ok else d.sent_at
    db.flush()
    return d
