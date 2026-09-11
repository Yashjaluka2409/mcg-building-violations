"""
SMS gateway abstraction.

`console` (default) prints messages to the log - use for demo/UAT.
`http`  posts to any DLT-registered gateway (NIC SMS, MSG91, Kaleyra ...) using a JSON body:
        {"sender": ..., "to": ..., "message": ..., "template_id": ...}
        Adapt `HttpSMSGateway.build_request` to the provider's exact contract (one method).
All notices are sent with a TRAI-DLT template id (SMS_DLT_TEMPLATE_*), which the IT team must
register once; the message text below follows the template variable order.
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings

log = logging.getLogger(__name__)


class SMSResult:
    def __init__(self, ok: bool, provider_ref: str = "", error: str = ""):
        self.ok, self.provider_ref, self.error = ok, provider_ref, error


class BaseSMSGateway:
    def send(self, to: str, message: str, template_id: str = "") -> SMSResult:  # pragma: no cover
        raise NotImplementedError


class ConsoleSMSGateway(BaseSMSGateway):
    def send(self, to, message, template_id=""):
        log.info("[SMS console] to=%s template=%s\n%s", to, template_id, message)
        return SMSResult(True, provider_ref="console")


class HttpSMSGateway(BaseSMSGateway):
    def __init__(self):
        self.cfg = settings.BVMS_SMS

    def build_request(self, to, message, template_id):
        headers = {"Content-Type": "application/json"}
        if self.cfg.get("HTTP_AUTH_HEADER"):
            k, _, v = self.cfg["HTTP_AUTH_HEADER"].partition(":")
            headers[k.strip()] = v.strip()
        body = {"sender": self.cfg.get("SENDER_ID"), "to": to, "message": message, "template_id": template_id}
        return self.cfg["HTTP_URL"], headers, body

    def send(self, to, message, template_id=""):
        url, headers, body = self.build_request(to, message, template_id)
        try:
            r = requests.request(self.cfg.get("HTTP_METHOD", "POST"), url, json=body, headers=headers, timeout=20)
            ok = 200 <= r.status_code < 300
            return SMSResult(ok, provider_ref=r.text[:120], error="" if ok else r.text[:500])
        except Exception as exc:  # pragma: no cover - network
            return SMSResult(False, error=str(exc))


def get_gateway() -> BaseSMSGateway:
    return HttpSMSGateway() if settings.BVMS_SMS.get("GATEWAY") == "http" else ConsoleSMSGateway()


def normalise_mobile(m: str) -> str:
    digits = "".join(ch for ch in (m or "") if ch.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits if len(digits) == 10 else ""


def scn_message(notice) -> str:
    verify = f"{settings.BVMS_PUBLIC_VERIFY_BASE.rstrip('/')}/{notice.verification_code}"
    due = notice.response_due_at.astimezone().strftime("%d-%m-%Y") if notice.response_due_at else "-"
    return (f"MCG: {notice.order_type.title_en.split(' (')[0]} No. {notice.notice_no} dated "
            f"{notice.issued_at.astimezone():%d-%m-%Y} issued for property {notice.case.pid or notice.case.address_line[:40]}. "
            f"Reply by {due}. View/verify: {verify} - Municipal Corporation Gurugram")


def order_message(notice) -> str:
    verify = f"{settings.BVMS_PUBLIC_VERIFY_BASE.rstrip('/')}/{notice.verification_code}"
    due = notice.compliance_due_at.astimezone().strftime("%d-%m-%Y") if notice.compliance_due_at else "-"
    return (f"MCG: {notice.order_type.title_en.split(' (')[0]} No. {notice.notice_no} dated "
            f"{notice.issued_at.astimezone():%d-%m-%Y} passed for property {notice.case.pid or notice.case.address_line[:40]}. "
            f"Comply by {due}. View/verify: {verify} - Municipal Corporation Gurugram")
