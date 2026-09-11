"""WhatsApp alerts through Aisensy (the platform's WhatsApp provider). Optional: active when AISENSY_API_KEY is set
and a campaign name is configured for the message kind (AISENSY_CAMPAIGN_SCN / AISENSY_CAMPAIGN_ORDER). The
campaign's approved template must take the same variables in the same order as `template_params` below:
    {{1}} notice title  {{2}} notice number  {{3}} date  {{4}} property  {{5}} due date  {{6}} verification link
"""
from __future__ import annotations

import logging

import requests

from app.core.config import settings
from app.core.timeutil import localtime

log = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(settings.AISENSY_API_KEY)


def campaign_for(is_scn: bool) -> str:
    return settings.AISENSY_CAMPAIGN_SCN if is_scn else settings.AISENSY_CAMPAIGN_ORDER


def send_template(destination_mobile: str, campaign_name: str, user_name: str, template_params: list[str]) -> tuple[bool, str, str]:
    """Returns (ok, provider_ref, error). Never raises."""
    if not enabled() or not campaign_name:
        return False, "", "Aisensy not configured"
    body = {"apiKey": settings.AISENSY_API_KEY, "campaignName": campaign_name, "destination": f"91{destination_mobile}", "userName": user_name or "Owner / occupier",
            "templateParams": [str(p) for p in template_params]}
    try:
        r = requests.post(settings.AISENSY_API_URL, json=body, timeout=20)
        ok = 200 <= r.status_code < 300
        return ok, r.text[:120], "" if ok else r.text[:500]
    except Exception as exc:  # pragma: no cover - network
        return False, "", str(exc)


def notice_params(notice, is_scn: bool) -> list[str]:
    due = notice.response_due_at if is_scn else notice.compliance_due_at
    return [notice.order_type.title_en.split(" (")[0], notice.notice_no, f"{localtime(notice.issued_at):%d-%m-%Y}",
            notice.case.pid or notice.case.address_line[:40], f"{localtime(due):%d-%m-%Y}" if due else "-",
            f"{settings.PUBLIC_VERIFY_BASE.rstrip('/')}/{notice.verification_code}"]
