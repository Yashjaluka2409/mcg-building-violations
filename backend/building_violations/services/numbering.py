"""Atomic, human-readable numbering.

Case number : MCG/BV/Z<zone>/<FY>/<000001>      e.g. MCG/BV/Z2/2026-27/000145
Notice no.  : MCG/BV/<TYPE>/<FY>/<000001>        e.g. MCG/BV/SCN/2026-27/000097
Verification code (printed under the QR): 12 characters, unambiguous alphabet.
"""
from __future__ import annotations

import secrets

from django.db import transaction
from django.utils import timezone

from ..models import Sequence

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def financial_year(dt=None) -> str:
    dt = dt or timezone.localtime()
    start = dt.year if dt.month >= 4 else dt.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def next_number(key: str) -> int:
    with transaction.atomic():
        seq, _ = Sequence.objects.select_for_update().get_or_create(key=key)
        seq.value += 1
        seq.save(update_fields=["value"])
        return seq.value


def next_case_no(zone_code: str | None) -> str:
    fy = financial_year()
    z = f"Z{zone_code}" if zone_code else "Z0"
    n = next_number(f"CASE:{z}:{fy}")
    return f"MCG/BV/{z}/{fy}/{n:06d}"


NOTICE_SHORT = {
    "SCN_261": "SCN", "SCN_408A": "SCN", "SCN_284": "SCN", "SCN_256_CANCELLATION": "SCN",
    "ALTERATION_NOTICE_263": "NTC", "REMOVAL_NOTICE_235": "NTC", "MISUSE_NOTICE_265": "NTC", "OC_NOTICE_264": "NTC",
    "STOP_WORK_262": "SWO", "SEALING_263A": "SEAL", "RESEALING_263A": "SEAL",
    "DEMOLITION_ORDER_261": "DEMO", "EVICTION_DEMOLITION_ORDER_408A": "DEMO", "DEMOLITION_ORDER_284": "DEMO",
    "DANGEROUS_BUILDING_ORDER_265": "ORD", "VACATE_ORDER_266": "ORD", "OC_REVOCATION_HBC_4_12": "ORD",
}


def next_notice_no(order_type_code: str) -> str:
    short = NOTICE_SHORT.get(order_type_code, "MEMO")
    fy = financial_year()
    n = next_number(f"NOTICE:{short}:{fy}")
    return f"MCG/BV/{short}/{fy}/{n:06d}"


def verification_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(12))
