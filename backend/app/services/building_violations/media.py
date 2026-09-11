"""Evidence files: store the bytes through the storage backend (S3 or local uploads), hash them, and compute the distance to the case point.
(The Django edition did the hash / size in a pre_save signal; here it is one explicit function.)"""
from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.integrations import storage
from app.core.timeutil import now
from app.models.building_violations import MediaAttachment
from app.services.building_violations import access
from app.services.building_violations.geo import haversine_m

IMAGE_EXT = {"jpg", "jpeg", "png", "heic", "webp"}
VIDEO_EXT = {"mp4", "mov", "m4v", "3gp", "webm"}
DOC_EXT = {"pdf", "doc", "docx", "xls", "xlsx"}


def media_type_for(filename: str) -> str:
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    return "IMAGE" if ext in IMAGE_EXT else "VIDEO" if ext in VIDEO_EXT else "PDF" if ext == "pdf" else "DOC" if ext in DOC_EXT else "OTHER"


def create_attachment(db: Session, *, data: bytes, filename: str, uploaded_by, kind: str = "INSPECTION", media_type: str | None = None,
                      case=None, notice=None, sanctioned_plan=None, task=None, latitude=None, longitude=None, accuracy_m=None, altitude_m=None,
                      captured_at=None, device_id: str = "", caption: str = "", integrity_check=None) -> MediaAttachment:
    relpath = storage.save_bytes(storage.media_upload_path(filename), data)
    tolerance = access.geotag_tolerance_m(db)   # read the setting before the row is built (autoflush ordering)
    att = MediaAttachment(
        case=case, notice=notice, sanctioned_plan=sanctioned_plan, task=task, kind=kind, media_type=media_type or media_type_for(filename), file=relpath,
        original_name=(filename or "")[:255], size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
        latitude=latitude, longitude=longitude, accuracy_m=accuracy_m, altitude_m=altitude_m, captured_at=captured_at or now(),
        device_id=(device_id or "")[:120], caption=caption or "", uploaded_by=uploaded_by,
        integrity_status=integrity_check.decision if integrity_check is not None else "UNVERIFIED", integrity_check=integrity_check,
    )
    db.add(att)
    if case is not None and case.latitude is not None and att.latitude is not None:
        att.distance_from_case_m = round(haversine_m(att.latitude, att.longitude, case.latitude, case.longitude), 2)
        att.geotag_verified = float(att.distance_from_case_m) <= tolerance
    db.flush()
    return att
