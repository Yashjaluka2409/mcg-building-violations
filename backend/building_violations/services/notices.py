"""Issue a notice/order: number it, render, hash, sign, store, dispatch SMS."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from ..integrations.sms import get_gateway, normalise_mobile, order_message, scn_message
from ..models import Notice, NoticeDispatch, OrderType, ViolationCase
from .numbering import next_notice_no, verification_code
from .pdf import html_to_pdf, render_notice_html, sha256_hex
from .signing import get_signer

log = logging.getLogger(__name__)

ORDER_KINDS_FINAL = {"DEMOLITION_ORDER_261", "EVICTION_DEMOLITION_ORDER_408A", "DEMOLITION_ORDER_284",
                     "DANGEROUS_BUILDING_ORDER_265", "VACATE_ORDER_266", "OC_REVOCATION_HBC_4_12"}
SCN_TYPES = {"SCN_261", "SCN_408A", "SCN_284", "SCN_256_CANCELLATION", "ALTERATION_NOTICE_263",
             "REMOVAL_NOTICE_235", "MISUSE_NOTICE_265", "OC_NOTICE_264"}


def build_notice(case: ViolationCase, order_type: OrderType, issued_by, *, addressee_name: str, addressee_address: str,
                 mobiles: list[str], response_days: int = 0, compliance_days: int = 0, hearing_at=None,
                 hearing_venue: str = "", operative_text_en: str = "", operative_text_hi: str = "",
                 is_final_order: bool = False, extra_context: dict | None = None) -> Notice:
    now = timezone.now()
    if order_type.min_days and (response_days or compliance_days):
        if order_type.kind == "NOTICE" and response_days < order_type.min_days:
            raise ValueError(f"Statutory minimum for {order_type.code} is {order_type.min_days} days")
        if order_type.kind == "ORDER" and compliance_days < order_type.min_days:
            raise ValueError(f"Statutory minimum for {order_type.code} is {order_type.min_days} days")
    mobiles = [m for m in (normalise_mobile(x) for x in mobiles) if m]
    n = Notice(
        case=case, order_type=order_type, notice_no=next_notice_no(order_type.code), kind=order_type.kind,
        issued_by=issued_by, issued_at=now, addressee_name=addressee_name or case.owner_name or "The Owner/Occupier",
        addressee_address=addressee_address or case.address_line, addressee_mobiles=mobiles,
        response_days=response_days, response_due_at=(now + timedelta(days=response_days)) if response_days else None,
        compliance_days=compliance_days, compliance_due_at=(now + timedelta(days=compliance_days)) if compliance_days else None,
        hearing_at=hearing_at, hearing_venue=hearing_venue,
        operative_text_en=operative_text_en or order_type.body_override_en, operative_text_hi=operative_text_hi or order_type.body_override_hi,
        verification_code=verification_code(), is_final_order=is_final_order,
    )
    n.qr_payload = f"{settings.BVMS_PUBLIC_VERIFY_BASE.rstrip('/')}/{n.verification_code}"
    n.save()
    render_and_sign(n, extra_context=extra_context)
    return n


def render_and_sign(notice: Notice, extra_context: dict | None = None) -> Notice:
    html = render_notice_html(notice, extra_context)
    notice.html_snapshot = html
    pdf_bytes = html_to_pdf(html)
    notice.document_hash = sha256_hex(pdf_bytes)
    notice.qr_payload = f"{settings.BVMS_PUBLIC_VERIFY_BASE.rstrip('/')}/{notice.verification_code}?h={notice.document_hash[:16]}"
    # re-render once so the QR embeds the hash prefix as well
    html = render_notice_html(notice, extra_context)
    notice.html_snapshot = html
    pdf_bytes = html_to_pdf(html)
    notice.document_hash = sha256_hex(pdf_bytes)
    fname = notice.notice_no.replace("/", "-")
    notice.pdf.save(f"{fname}.pdf", ContentFile(pdf_bytes), save=False)
    signer = get_signer()
    issuer = getattr(notice.issued_by, "bvms_profile", None)
    signer_name = issuer.display_name if issuer else str(notice.issued_by)
    res = signer.sign(pdf_bytes, reason=f"{notice.order_type.code} {notice.notice_no}", signer_name=signer_name)
    if res.ok and res.pdf:
        notice.signed_pdf.save(f"{fname}-signed.pdf", ContentFile(res.pdf), save=False)
        notice.signature_status = Notice.SignatureStatus.SIGNED
        notice.signer_name, notice.signer_cert_subject, notice.signer_cert_serial = res.signer_name, res.subject[:300], res.serial[:120]
        notice.signed_at = timezone.now()
        notice.signature_error = ""
    else:
        notice.signature_status = Notice.SignatureStatus.FAILED
        notice.signature_error = res.error[:2000]
    notice.save()
    return notice


def dispatch_sms(notice: Notice) -> list[NoticeDispatch]:
    gw = get_gateway()
    cfg = settings.BVMS_SMS
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
        d.sent_at = timezone.now() if res.ok else None
        d.save()
        out.append(d)
    return out


def retry_dispatch(d: NoticeDispatch):
    gw = get_gateway()
    res = gw.send(d.to, d.message, "")
    d.attempts += 1
    d.status = "SENT" if res.ok else "FAILED"
    d.provider_ref, d.last_error = res.provider_ref[:120], res.error[:2000]
    d.sent_at = timezone.now() if res.ok else d.sent_at
    d.save()
    return d
