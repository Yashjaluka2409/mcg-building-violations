"""Orders issued before the system (paper demolition / sealing / eviction orders) - see services/legacy.py.

POST legacy-orders/                      record one paper order (JSON) -> case detail
POST legacy-orders/bulk/                 multipart {file: CSV/XLSX with the template columns, title, order_reference} -> batch result
GET  legacy-orders/template/             CSV template with one example row
GET  legacy-orders/                      the imported orders (cases with source=LEGACY_ORDER, jurisdiction-scoped) ?status=&ward=&search=
GET  legacy-orders/summary/              counts by status
GET  legacy-orders/batches/              import batches with their row errors
POST legacy-orders/{case_id}/status/     record a historical status change from the paper file
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile
from app.routers.building_violations._router import SyncRouter
from sqlalchemy import or_

from app.integrations import storage
from app.core.errors import WorkflowError
from app.models import building_violations as m
from app.db.util import to_uuid
from app.services.building_violations import access, legacy
from app.schemas.building_violations import inputs as s
from app.schemas.building_violations import outputs as ser
from app.core.http import csv_response, paginate, read_table_upload, resp
from app.routers.building_violations.deps import DB, Officer, check_perm
from app.repositories.building_violations import case_criteria, with_list_loads

router = SyncRouter(prefix="/legacy-orders")
C = m.ViolationCase


def _crit(db, user):
    return case_criteria(db, user) + [C.source == legacy.LEGACY_SOURCE]


def _may_manage(db, user):
    if not (user.bvms_profile.role in access.MANAGEMENT_ROLES or access.has_perm(db, user, "LEGACY_ORDERS_MANAGE")):
        return resp({"detail": "Requires permission: LEGACY_ORDERS_MANAGE"}, 403)
    return None


@router.get("/")
def list_orders(request: Request, user: Officer, db: DB):
    p = request.query_params
    q = with_list_loads(db.query(C).filter(*_crit(db, user)))
    if p.get("status"):
        q = q.filter(C.status.in_(p["status"].split(",")))
    if p.get("ward"):
        q = q.filter(C.ward_id == int(p["ward"]))
    if p.get("zone"):
        q = q.filter(C.zone_id == int(p["zone"]))
    if p.get("search"):
        like = f"%{p['search']}%"
        q = q.outerjoin(m.Notice, C.final_order_id == m.Notice.id).filter(or_(C.case_no.ilike(like), C.pid.ilike(like), C.address_line.ilike(like), C.owner_name.ilike(like), m.Notice.notice_no.ilike(like), C.legacy_reference.ilike(like)))
    ordering = (p.get("ordering") or "-order_issued_at").strip()
    col = getattr(C, ordering.lstrip("-"), None) or C.order_issued_at
    q = q.order_by(col.desc() if ordering.startswith("-") else col.asc(), C.created_at.desc())
    return resp(paginate(request, q, lambda c: ser.case_list(c, request)))


@router.post("/", status_code=201)
def create_order(body: s.LegacyOrderIn, request: Request, user: Officer, db: DB):
    denied = _may_manage(db, user)
    if denied:
        return denied
    d = body.model_dump()
    d["violations"] = [v for v in d.get("violations") or []]
    case = legacy.import_order(db, user, d, request=request)
    db.flush()
    db.expire(case)
    return resp(ser.case_detail(db, case, request, user), 201)


@router.get("/summary/")
def summary(user: Officer, db: DB):
    return resp(legacy.summary(db, _crit(db, user)))


@router.get("/template/")
def template(user: Officer):
    return csv_response("legacy_orders_template.csv", legacy.TEMPLATE_COLUMNS, [], example=legacy.TEMPLATE_EXAMPLE)


@router.get("/batches/")
def batches(user: Officer, db: DB):
    check_perm(db, user, "LEGACY_ORDERS_MANAGE")
    return resp([ser.legacy_batch(b) for b in db.query(m.LegacyOrderBatch).order_by(m.LegacyOrderBatch.id.desc()).limit(50)])


@router.post("/bulk/", status_code=201)
def bulk(request: Request, user: Officer, db: DB, file: UploadFile | None = File(None), title: str | None = Form(None), order_reference: str | None = Form(None)):
    check_perm(db, user, "LEGACY_ORDERS_MANAGE")
    if file is None:
        return resp({"detail": "Upload a CSV or XLSX file (download the template first)"}, 400)
    raw = file.file.read()
    rows = read_table_upload(file.filename or "", raw)
    rel = storage.save_bytes(storage.dated_path("bvms/legacy", file.filename or "register.csv"), raw)
    batch = legacy.import_rows(db, user, rows, title=title or file.filename or "", source_file=rel, request=request, order_reference=order_reference or "")
    return resp(ser.legacy_batch(batch), 201)


@router.post("/{pk}/status/")
def update_status(pk: str, body: s.LegacyStatusUpdateIn, request: Request, user: Officer, db: DB):
    u = to_uuid(pk)
    case = db.query(C).filter(*_crit(db, user), C.id == u).first() if u else None
    if not case:
        return resp({"detail": "Not found"}, 404)
    legacy.update_status(db, case, user, body.model_dump(), request=request)
    db.flush()
    db.expire(case)
    return resp(ser.case_detail(db, case, request, user))
