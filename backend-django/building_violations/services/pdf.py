"""
Notice / order PDF generation.

* Template: Django HTML template per order type (templates/notices/<template>.html) rendered with a
  bilingual context, plus a QR code (verification URL + document hash) and the officer block.
* Renderer: WeasyPrint (proper Devanagari shaping) when available; reportlab fallback otherwise.
* Output: unsigned PDF bytes + SHA-256; the signing service then embeds a PAdES signature.
"""
from __future__ import annotations

import base64
import hashlib
import io
import logging
from pathlib import Path

import qrcode
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

log = logging.getLogger(__name__)


def make_qr_png(payload: str) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#4a153f", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _font_face_css() -> str:
    d = Path(settings.BVMS_FONTS_DIR)
    css = []
    lat = d / "NotoSans-Variable.ttf"
    dev = d / "NotoSansDevanagari-Variable.ttf"
    if lat.exists():
        css.append(f"@font-face {{ font-family: 'NotoSans'; src: url('file://{lat}'); font-weight: 100 900; }}")
    if dev.exists():
        css.append(f"@font-face {{ font-family: 'NotoDev'; src: url('file://{dev}'); font-weight: 100 900; }}")
    return "\n".join(css)


def render_notice_html(notice, extra_context: dict | None = None) -> str:
    case = notice.case
    corp = settings.BVMS_CORPORATION
    verify_url = f"{settings.BVMS_PUBLIC_VERIFY_BASE.rstrip('/')}/{notice.verification_code}"
    qr_payload = notice.qr_payload or verify_url
    qr_b64 = base64.b64encode(make_qr_png(qr_payload)).decode()
    issuer = getattr(notice.issued_by, "bvms_profile", None)
    sections = _legal_sections_for(case)
    ctx = {
        "notice": notice, "case": case, "corp": corp, "verify_url": verify_url, "qr_b64": qr_b64,
        "issuer": issuer, "issuer_name": (issuer.display_name if issuer else str(notice.issued_by)),
        "violations": list(case.violations.select_related("violation_type")),
        "legal_sections": sections,
        "sanctioned_plan": case.sanctioned_plan,
        "font_css": _font_face_css(),
        "now": timezone.localtime(),
        "issued_local": timezone.localtime(notice.issued_at),
        "response_due_local": timezone.localtime(notice.response_due_at) if notice.response_due_at else None,
        "compliance_due_local": timezone.localtime(notice.compliance_due_at) if notice.compliance_due_at else None,
        "hearing_local": timezone.localtime(notice.hearing_at) if notice.hearing_at else None,
        "order_type": notice.order_type,
    }
    ctx.update(extra_context or {})
    template = f"notices/{notice.order_type.template}"
    try:
        return render_to_string(template, ctx)
    except Exception:
        log.warning("Template %s missing; using generic template", template)
        return render_to_string("notices/generic.html", ctx)


def _legal_sections_for(case):
    from ..models import LegalSection
    keys = set()
    for cv in case.violations.select_related("violation_type"):
        for b in cv.violation_type.legal_basis or []:
            keys.add((b.get("statute"), b.get("section")))
    out = []
    for st, sect in sorted(keys, key=lambda k: (k[0] or "", k[1] or "")):
        ls = LegalSection.objects.filter(statute_id=st, section=sect).first()
        if ls:
            out.append(ls)
    return out


def html_to_pdf(html: str) -> bytes:
    try:
        from weasyprint import HTML  # noqa
        return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
    except Exception as exc:  # WeasyPrint not installed or Pango missing
        log.warning("WeasyPrint unavailable (%s); using reportlab fallback (English only)", exc)
        return _reportlab_fallback(html)


def _reportlab_fallback(html: str) -> bytes:
    import re
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    text = re.sub(r"<style.*?</style>", "", html, flags=re.S)
    text = re.sub(r"<img[^>]*>", "", text)
    text = re.sub(r"</(p|div|h[1-6]|tr|li)>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    st = getSampleStyleSheet()
    story = []
    for ln in lines:
        safe = ln.replace("&", "&amp;").replace("<", "&lt;")
        story.append(Paragraph(safe, st["Normal"]))
        story.append(Spacer(1, 3))
    doc.build(story)
    return buf.getvalue()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
