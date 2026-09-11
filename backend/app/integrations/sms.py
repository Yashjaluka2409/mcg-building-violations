"""
SMS gateway abstraction (DLT-registered, MCG sender id MCGGGN).

`console`  (default) prints messages to the log - use for demo/UAT.
`pixabits` the platform's gateway (Pixabits). `PixabitsSMSGateway.build_request` holds the one place where the
           request is shaped; align it with the platform's existing Pixabits helper (auth key, route, DLT ids)
           or, when the module runs inside the platform backend, call that helper from `get_gateway()`.
`http`     any other JSON HTTP gateway (NIC SMS, MSG91, Kaleyra ...): {"sender", "to", "message", "template_id"}.
All notices are sent with a TRAI-DLT template id (SMS_DLT_TEMPLATE_*), which the IT team must register once;
the message text below follows the template variable order.
"""
from __future__ import annotations

import logging

import requests

from app.core.config import settings
from app.core.timeutil import localtime

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
        self.cfg = settings.sms

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


class PixabitsSMSGateway(BaseSMSGateway):
    """Pixabits transactional SMS (DLT). Query-string HTTP API with auth key, sender id, route and DLT template id."""

    def __init__(self):
        self.cfg = settings.sms

    def build_request(self, to, message, template_id):
        params = {"authkey": self.cfg.get("PIXABITS_API_KEY", ""), "mobiles": f"91{to}", "message": message, "sender": self.cfg.get("SENDER_ID", "MCGGGN"),
                  "route": self.cfg.get("PIXABITS_ROUTE", "4"), "country": "91"}
        if template_id:
            params["DLT_TE_ID"] = template_id
        return self.cfg.get("PIXABITS_API_URL", ""), params

    def send(self, to, message, template_id=""):
        url, params = self.build_request(to, message, template_id)
        if not url or not params.get("authkey"):
            return SMSResult(False, error="Pixabits gateway not configured (PIXABITS_API_URL / PIXABITS_API_KEY)")
        try:
            r = requests.get(url, params=params, timeout=20)
            ok = 200 <= r.status_code < 300 and "error" not in r.text.lower()[:200]
            return SMSResult(ok, provider_ref=r.text[:120], error="" if ok else r.text[:500])
        except Exception as exc:  # pragma: no cover - network
            return SMSResult(False, error=str(exc))


def get_gateway() -> BaseSMSGateway:
    kind = (settings.sms.get("GATEWAY") or "console").lower()
    if kind == "http":
        return HttpSMSGateway()
    if kind == "pixabits":
        return PixabitsSMSGateway()
    return ConsoleSMSGateway()


def normalise_mobile(m: str) -> str:
    digits = "".join(ch for ch in (m or "") if ch.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits if len(digits) == 10 else ""


def scn_message(notice) -> str:
    verify = f"{settings.PUBLIC_VERIFY_BASE.rstrip('/')}/{notice.verification_code}"
    due = localtime(notice.response_due_at).strftime("%d-%m-%Y") if notice.response_due_at else "-"
    return (f"MCG: {notice.order_type.title_en.split(' (')[0]} No. {notice.notice_no} dated "
            f"{localtime(notice.issued_at):%d-%m-%Y} issued for property {notice.case.pid or notice.case.address_line[:40]}. "
            f"Reply by {due}. View/verify: {verify} - Municipal Corporation Gurugram")


def order_message(notice) -> str:
    verify = f"{settings.PUBLIC_VERIFY_BASE.rstrip('/')}/{notice.verification_code}"
    due = localtime(notice.compliance_due_at).strftime("%d-%m-%Y") if notice.compliance_due_at else "-"
    return (f"MCG: {notice.order_type.title_en.split(' (')[0]} No. {notice.notice_no} dated "
            f"{localtime(notice.issued_at):%d-%m-%Y} passed for property {notice.case.pid or notice.case.address_line[:40]}. "
            f"Comply by {due}. View/verify: {verify} - Municipal Corporation Gurugram")
