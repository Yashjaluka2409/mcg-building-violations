"""Atomic, human-readable numbering.

Case number : MCG/BV/Z<zone>/<FY>/<000001>      e.g. MCG/BV/Z2/2026-27/000145
Notice no.  : MCG/BV/<TYPE>/<FY>/<000001>        e.g. MCG/BV/SCN/2026-27/000097
Verification code (printed under the QR): 12 characters, unambiguous alphabet.
"""
from __future__ import annotations

import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.timeutil import localtime
from app.models.building_violations import Sequence

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def financial_year(dt=None) -> str:
    dt = dt or localtime()
    start = dt.year if dt.month >= 4 else dt.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def next_number(db: Session, key: str) -> int:
    seq = db.query(Sequence).filter(Sequence.key == key).with_for_update().first()
    if seq is None:
        try:
            with db.begin_nested():
                db.add(Sequence(key=key, value=0))
                db.flush()
        except IntegrityError:  # another worker created it in the meantime
            pass
        seq = db.query(Sequence).filter(Sequence.key == key).with_for_update().first()
    seq.value += 1
    db.flush()
    return seq.value


def next_case_no(db: Session, zone_code: str | None) -> str:
    fy = financial_year()
    z = f"Z{zone_code}" if zone_code else "Z0"
    n = next_number(db, f"CASE:{z}:{fy}")
    return f"MCG/BV/{z}/{fy}/{n:06d}"


NOTICE_SHORT = {
    "SCN_261": "SCN", "SCN_408A": "SCN", "SCN_284": "SCN", "SCN_256_CANCELLATION": "SCN",
    "ALTERATION_NOTICE_263": "NTC", "REMOVAL_NOTICE_235": "NTC", "MISUSE_NOTICE_265": "NTC", "OC_NOTICE_264": "NTC",
    "STOP_WORK_262": "SWO", "SEALING_263A": "SEAL", "RESEALING_263A": "SEAL",
    "DEMOLITION_ORDER_261": "DEMO", "EVICTION_DEMOLITION_ORDER_408A": "DEMO", "DEMOLITION_ORDER_284": "DEMO",
    "DANGEROUS_BUILDING_ORDER_265": "ORD", "VACATE_ORDER_266": "ORD", "OC_REVOCATION_HBC_4_12": "ORD",
}


def next_notice_no(db: Session, order_type_code: str) -> str:
    short = NOTICE_SHORT.get(order_type_code, "MEMO")
    fy = financial_year()
    n = next_number(db, f"NOTICE:{short}:{fy}")
    return f"MCG/BV/{short}/{fy}/{n:06d}"


def verification_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(12))
