"""Evidence upload / listing / deletion.

POST multipart {file, kind, case?, notice?, sanctioned_plan?, task?, latitude, longitude, accuracy_m, altitude_m,
captured_at, device_id, caption, location_integrity(JSON)}. The mobile app captures photos/videos in-app and posts
the GPS fix read at capture time; the server checks the fix for spoofing, stores it, hashes the file and (when a
case is given) computes the distance to the case point."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from app.routers.building_violations._router import SyncRouter

from app.integrations import storage
from app.core.errors import WorkflowError
from app.core.timeutil import aware, make_aware_local
from app.models import building_violations as m
from app.db.util import device_id_of, to_uuid
from app.services.building_violations import location_integrity as li
from app.services.building_violations.audit import record_event
from app.services.building_violations.media import create_attachment, media_type_for
from app.schemas.building_violations import outputs as ser
from app.core.http import apply_filters, form_json, paginate, resp
from app.routers.building_violations.deps import DB, Officer

router = SyncRouter(prefix="/media")


def _dec(v, name):
    if v in (None, ""):
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        raise WorkflowError(f"{name}: A valid number is required.")


def _dt(v):
    if v in (None, ""):
        return None
    try:
        return make_aware_local(datetime.fromisoformat(str(v).replace("Z", "+00:00")))
    except ValueError:
        raise WorkflowError("captured_at: Datetime has wrong format.")


def _ref(db, model, raw, name):
    if raw in (None, ""):
        return None
    pk = to_uuid(raw) if model in (m.ViolationCase, m.Notice) else raw
    try:
        o = db.get(model, pk if model in (m.ViolationCase, m.Notice) else int(raw))
    except (ValueError, TypeError):
        o = None
    if o is None:
        raise WorkflowError(f'{name}: Invalid pk "{raw}" - object does not exist.')
    return o


@router.get("/")
def list_media(request: Request, user: Officer, db: DB):
    q = apply_filters(db.query(m.MediaAttachment), m.MediaAttachment, request.query_params, ("case", "kind", "notice", "sanctioned_plan", "task"))
    q = q.order_by(m.MediaAttachment.created_at.desc())
    return resp(paginate(request, q, lambda x: ser.media(x, request)))


@router.post("/", status_code=201)
def upload(request: Request, user: Officer, db: DB, file: UploadFile = File(...), kind: str = Form("INSPECTION"), case: str | None = Form(None), notice: str | None = Form(None),
           sanctioned_plan: str | None = Form(None), task: str | None = Form(None), latitude: str | None = Form(None), longitude: str | None = Form(None),
           accuracy_m: str | None = Form(None), altitude_m: str | None = Form(None), captured_at: str | None = Form(None), device_id: str | None = Form(None),
           caption: str | None = Form(None), location_integrity: str | None = Form(None)):
    if kind not in m.MediaKind.values:
        raise WorkflowError(f'kind: "{kind}" is not a valid choice.')
    name = file.filename or "upload"
    media_type = media_type_for(name)
    if media_type == "OTHER":
        ext = (name.rsplit(".", 1)[-1] if "." in name else "").lower()
        return resp({"detail": f"Unsupported file type .{ext}"}, 400)
    case_o, notice_o = _ref(db, m.ViolationCase, case, "case"), _ref(db, m.Notice, notice, "notice")
    plan_o, task_o = _ref(db, m.SanctionedPlan, sanctioned_plan, "sanctioned_plan"), _ref(db, m.InspectionTask, task, "task")
    lat, lng = _dec(latitude, "latitude"), _dec(longitude, "longitude")
    acc, alt, cap = _dec(accuracy_m, "accuracy_m"), _dec(altitude_m, "altitude_m"), _dt(captured_at)
    dev = device_id or device_id_of(request)
    chk = None
    if lat is not None and lng is not None:
        # Anti-spoofing: refuse (HTTP 400) before anything is stored when the geotag cannot be trusted.
        chk = li.evaluate(db, user=user, request=request, context="MEDIA_UPLOAD", latitude=lat, longitude=lng, accuracy_m=acc, altitude_m=alt, captured_at=cap,
                          signals=form_json(location_integrity), case=case_o, task=task_o, device_id=dev)
    data = file.file.read()
    att = create_attachment(db, data=data, filename=name, uploaded_by=user, kind=kind, media_type=media_type, case=case_o, notice=notice_o, sanctioned_plan=plan_o, task=task_o,
                            latitude=lat, longitude=lng, accuracy_m=acc, altitude_m=alt, captured_at=cap, device_id=dev, caption=caption or "", integrity_check=chk)
    if chk is not None:
        chk.media_id = att.id
        db.flush()
    if case_o is not None:
        record_event(db, case_o, "MEDIA_ADDED", actor=user, from_status=case_o.status, to_status=case_o.status, request=request,
                     payload={"media_id": str(att.id), "kind": att.kind, "type": media_type, "geotag_verified": att.geotag_verified,
                              "integrity": att.integrity_status, "integrity_flags": (chk.flags if chk else [])}, lat=att.latitude, lng=att.longitude)
    return resp(ser.media(att, request), 201)


@router.get("/{pk}/")
def media_detail(pk: str, request: Request, user: Officer, db: DB):
    att = db.get(m.MediaAttachment, to_uuid(pk)) if to_uuid(pk) else None
    if not att:
        raise HTTPException(404, "Not found.")
    return resp(ser.media(att, request))


@router.delete("/{pk}/", status_code=204)
def media_delete(pk: str, user: Officer, db: DB):
    att = db.get(m.MediaAttachment, to_uuid(pk)) if to_uuid(pk) else None
    if not att:
        raise HTTPException(404, "Not found.")
    # evidence is never hard-deleted once the case has left DRAFT
    if att.case is not None and att.case.status != "DRAFT":
        raise WorkflowError("Evidence cannot be deleted after the case is submitted", 403)
    rel = att.file
    db.delete(att)
    db.flush()
    storage.delete(rel)
    return resp(None, 204)
