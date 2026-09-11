"""Planned inspections pushed by the JC / AE to the field (single, bulk CSV/XLSX, map point)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from app.routers.building_violations._router import SyncRouter
from sqlalchemy import and_, or_

from app.integrations import storage
from app.core.errors import WorkflowError
from app.core.timeutil import now
from app.models import building_violations as m
from app.db.util import to_uuid
from app.services.building_violations import access
from app.services.building_violations import location_integrity as li
from app.services.building_violations import tasks as ts
from app.schemas.building_violations import inputs as s
from app.schemas.building_violations import outputs as ser
from app.core.http import apply_filters, apply_ordering, apply_search, csv_response, paginate, read_table_upload, resp
from app.routers.building_violations.deps import DB, Officer, check_perm

router = SyncRouter(prefix="/inspections")
T = m.InspectionTask
TEMPLATE_COLS = ["pid", "address", "latitude", "longitude", "ward_number", "owner_name", "owner_mobile", "category", "instructions", "priority", "assign_to_mobile"]
TEMPLATE_EXAMPLE = ["GGN012345", "H.No. 123, Sector 14", "28.4700", "77.0450", "19", "Ramesh Kumar", "9811100001", "PG_HOSTEL",
                    "Verify whether the building is run as a paying-guest accommodation without change of use; count rooms and occupants; check fire exits.", "NORMAL", "9000000001"]
OPEN = ["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"]


def scoped(db, user, params):
    prof = user.bvms_profile
    zone_ids = [z.id for z in prof.zones]
    ward_ids = [w.id for w in prof.wards]
    q = db.query(T)
    if access.has_perm(db, user, "TASKS_VIEW_ALL") or prof.role in access.MANAGEMENT_ROLES:
        pass
    elif access.has_perm(db, user, "TASKS_ASSIGN"):
        q = q.filter(or_(T.created_by_id == user.id, T.zone_id.in_(zone_ids) if zone_ids else False))
    else:
        q = q.filter(or_(T.assigned_to_id == user.id,
                         and_(T.assigned_to_id.is_(None), T.zone_id.in_(zone_ids)) if zone_ids else False,
                         and_(T.assigned_to_id.is_(None), T.ward_id.in_(ward_ids)) if ward_ids else False))
    if params.get("mine") == "1":
        q = q.filter(T.assigned_to_id == user.id)
    if params.get("open") == "1":
        q = q.filter(T.status.in_(OPEN))
    if params.get("overdue") == "1":
        q = q.filter(T.status.in_(OPEN), T.due_at < now())
    return q


def get_task(db, user, pk, params=None) -> T:
    t = scoped(db, user, params or {}).filter(T.id == pk).first()
    if not t:
        raise HTTPException(404, "Not found.")
    return t


def _ok(db, t, request):
    db.flush()
    db.expire(t)
    return resp(ser.inspection_task(db, t, request))


def _user(db, pk):
    if pk is None:
        return None
    u = db.get(m.User, pk)
    if not u:
        raise WorkflowError(f'Invalid pk "{pk}" - object does not exist.')
    return u


@router.get("/tasks/")
def list_tasks(request: Request, user: Officer, db: DB):
    p = request.query_params
    q = apply_filters(scoped(db, user, p), T, p, ("status", "category", "assigned_to", "batch", "ward", "zone", "priority", "created_by"))
    q = q.outerjoin(m.InspectionBatch, T.batch_id == m.InspectionBatch.id)
    q = apply_search(q, p, [T.pid, T.address, T.owner_name, T.instructions, m.InspectionBatch.title])
    q = apply_ordering(q, p, {k: getattr(T, k) for k in ("created_at", "due_at", "assigned_at", "completed_at")}, [T.created_at.desc(), T.id.desc()])
    return resp(paginate(request, q, lambda t: ser.inspection_task(db, t, request)))


@router.post("/tasks/", status_code=201)
def create_task(body: s.TaskCreateIn, request: Request, user: Officer, db: DB):
    d = body.model_dump()
    d["assigned_to"] = _user(db, d.get("assigned_to"))
    d["ward"] = db.get(m.Ward, d["ward"]) if d.get("ward") else None
    if d.get("related_case"):
        d["related_case"] = db.get(m.ViolationCase, d["related_case"])
    t = ts.create_task(db, user, **d)
    return resp(ser.inspection_task(db, t, request), 201)


@router.get("/tasks/counts/")
def counts(request: Request, user: Officer, db: DB):
    q = scoped(db, user, request.query_params)
    t = now()
    n = lambda *f: q.filter(*f).order_by(None).count()  # noqa: E731
    return resp({"assigned_to_me": n(T.assigned_to_id == user.id, T.status.in_(["ASSIGNED", "IN_PROGRESS"])), "open": n(T.status.in_(OPEN)), "unassigned": n(T.status == "UNASSIGNED"),
                 "overdue": n(T.status.in_(OPEN), T.due_at < t), "violation_recorded": n(T.status == "VIOLATION_RECORDED"), "no_violation": n(T.status == "NO_VIOLATION")})


@router.get("/tasks/geojson/")
def geojson(request: Request, user: Officer, db: DB):
    p = request.query_params
    q = apply_filters(scoped(db, user, p), T, p, ("status", "category", "assigned_to", "batch", "ward", "zone", "priority", "created_by")).filter(T.latitude.isnot(None))
    feats = []
    for t in q.order_by(T.id.desc()).limit(5000):
        a, c = t.assigned_to, t.case
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(t.longitude), float(t.latitude)]},
                      "properties": {"id": t.id, "kind": "task", "pid": t.pid, "address": t.address, "status": t.status, "category": t.category,
                                     "assigned_to": a.bvms_profile.display_name if a is not None and getattr(a, "bvms_profile", None) else None,
                                     "due_at": t.due_at, "case_id": str(c.id) if c else None, "case_no": c.case_no if c else None}})
    return resp({"type": "FeatureCollection", "features": feats})


@router.get("/tasks/template/")
def template(user: Officer):
    return csv_response("planned_inspections_template.csv", TEMPLATE_COLS, [], example=TEMPLATE_EXAMPLE)


@router.post("/tasks/bulk_upload/", status_code=201)
def bulk_upload(request: Request, user: Officer, db: DB, file: UploadFile = File(...), title: str | None = Form(None), category: str | None = Form(None),
                instructions: str | None = Form(None), due_days: str | None = Form(None), assign_to: str | None = Form(None), lookup_pid: str = Form("1")):
    """multipart: file (CSV/XLSX with the template columns), title, category, instructions, due_days, assign_to (user id, optional), lookup_pid (1/0)."""
    check_perm(db, user, "TASKS_ASSIGN")
    data = file.file.read()
    rows = read_table_upload(file.filename or "", data)
    assignee = _user(db, to_uuid(assign_to)) if assign_to else None
    rel = storage.save_bytes(storage.dated_path("bvms/inspection-batches", file.filename or "batch.csv"), data)
    batch = ts.bulk_create_from_rows(db, user, rows, title=title or f"Batch {datetime.now():%d-%m-%Y %H:%M}", category=category or "VERIFICATION", instructions=instructions or "",
                                     due_days=int(due_days or 7), source_file=rel, default_assignee=assignee, lookup_pid=str(lookup_pid) != "0")
    return resp(ser.inspection_batch(db, batch), 201)


@router.get("/tasks/{pk}/")
def task_detail(pk: int, request: Request, user: Officer, db: DB):
    return resp(ser.inspection_task(db, get_task(db, user, pk), request))


@router.patch("/tasks/{pk}/")
def task_update(pk: int, body: s.TaskUpdateIn, request: Request, user: Officer, db: DB):
    check_perm(db, user, "TASKS_ASSIGN")
    t = get_task(db, user, pk)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(t, k, v)
    return _ok(db, t, request)


@router.post("/tasks/{pk}/assign/")
def assign(pk: int, body: s.TaskAssignIn, request: Request, user: Officer, db: DB):
    t = get_task(db, user, pk)
    ts.assign_task(db, t, user, _user(db, body.assigned_to), body.remarks)
    return _ok(db, t, request)


@router.post("/tasks/{pk}/start/")
def start(pk: int, body: s.TaskStartIn, request: Request, user: Officer, db: DB):
    """Field officer on site. Body: {latitude, longitude, accuracy_m}. 400 if outside the geofence."""
    t = get_task(db, user, pk)
    li.evaluate(db, user=user, request=request, context="TASK_START", latitude=body.latitude, longitude=body.longitude, accuracy_m=body.accuracy_m, signals=body.location_integrity, task=t)
    ts.start_task(db, t, user, latitude=body.latitude, longitude=body.longitude, accuracy_m=body.accuracy_m)
    return _ok(db, t, request)


@router.get("/tasks/{pk}/distance/")
def distance(pk: int, request: Request, user: Officer, db: DB):
    """Client pre-check: ?lat&lng -> {distance_m, geofence_m, within}."""
    t = get_task(db, user, pk)
    try:
        lat, lng = float(request.query_params["lat"]), float(request.query_params["lng"])
    except (KeyError, ValueError):
        return resp({"detail": "lat and lng required"}, 400)
    dist = ts.distance_to_task(t, lat, lng)
    fence = ts.geofence_m(db, t)
    return resp({"distance_m": dist, "geofence_m": fence, "within": dist is None or dist <= fence})


@router.post("/tasks/{pk}/close/")
def close(pk: int, body: s.TaskCloseIn, request: Request, user: Officer, db: DB):
    t = get_task(db, user, pk)
    if body.latitude is not None and body.longitude is not None:
        li.evaluate(db, user=user, request=request, context="TASK_CLOSE", latitude=body.latitude, longitude=body.longitude, signals=body.location_integrity, task=t)
    ts.complete_task_no_violation(db, t, user, outcome=body.outcome, remarks=body.remarks, media_ids=body.media_ids, latitude=body.latitude, longitude=body.longitude)
    return _ok(db, t, request)


@router.post("/tasks/{pk}/cancel/")
def cancel(pk: int, request: Request, user: Officer, db: DB, body: s.TaskCancelIn | None = None):
    t = get_task(db, user, pk)
    ts.cancel_task(db, t, user, (body.remarks if body else "") or "")
    return _ok(db, t, request)


# ---------------------------------------------------------------- batches
@router.get("/batches/")
def batches(request: Request, user: Officer, db: DB):
    check_perm(db, user, "TASKS_ASSIGN", "TASKS_VIEW_ALL")
    q = db.query(m.InspectionBatch).order_by(m.InspectionBatch.created_at.desc(), m.InspectionBatch.id.desc())
    return resp(paginate(request, q, lambda b: ser.inspection_batch(db, b)))


@router.get("/batches/{pk}/")
def batch_detail(pk: int, user: Officer, db: DB):
    check_perm(db, user, "TASKS_ASSIGN", "TASKS_VIEW_ALL")
    b = db.get(m.InspectionBatch, pk)
    if not b:
        raise HTTPException(404, "Not found.")
    return resp(ser.inspection_batch(db, b))
