"""PID lookup, government-land layers and point checks."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from app.routers.building_violations._router import SyncRouter

from app.integrations import storage
from app.core.errors import WorkflowError
from app.models import building_violations as m
from app.integrations.pid import get_pid_client
from app.services.building_violations import access
from app.services.building_violations.geo import geojson_bbox, parcels_containing, ward_for_point
from app.services.building_violations.geo_import import import_layer
from app.schemas.building_violations import inputs as s
from app.schemas.building_violations import outputs as ser
from app.core.http import apply_filters, apply_search, paginate, resp
from app.routers.building_violations.deps import DB, Officer, check_perm

router = SyncRouter()


@router.get("/property/pid/{pid}/")
def pid_lookup(pid: str, user: Officer):
    rec = get_pid_client().lookup(pid)
    if not rec:
        return resp({"detail": "Property not found for the given PID."}, 404)
    return resp(rec.as_dict())


def _latlng(request):
    try:
        return float(request.query_params["lat"]), float(request.query_params["lng"])
    except (KeyError, ValueError):
        return None


@router.get("/property/nearby/")
def pid_nearby(request: Request, user: Officer):
    ll = _latlng(request)
    if not ll:
        return resp({"detail": "lat and lng are required"}, 400)
    return resp([r.as_dict() for r in get_pid_client().nearby(*ll)])


@router.get("/gis/check-point/")
def check_point(request: Request, user: Officer, db: DB):
    """Given a point: government-land parcels containing it, ward, land type."""
    ll = _latlng(request)
    if not ll:
        return resp({"detail": "lat and lng are required"}, 400)
    buffer = float(request.query_params.get("buffer_m", 0))
    parcels = parcels_containing(db, ll[0], ll[1], buffer)
    w = ward_for_point(db, ll[0], ll[1])
    land_type = "PRIVATE"
    if parcels:
        land_type = "GOVT_MCG" if parcels[0].agency == "MCG" else "GOVT_STATE"
    return resp({"land_type": land_type, "parcels": [ser.govt_parcel(p) for p in parcels], "ward": ser.ward(w) if w else None})


# ---------------------------------------------------------------- government-land parcels
@router.get("/gis/govt-land/")
def parcels(request: Request, user: Officer, db: DB):
    p = request.query_params
    q = apply_filters(db.query(m.GovtLandParcel), m.GovtLandParcel, p, ("agency", "ward", "active", "village"))
    q = apply_search(q, p, [m.GovtLandParcel.name, m.GovtLandParcel.khasra_no, m.GovtLandParcel.village, m.GovtLandParcel.land_use]).order_by(m.GovtLandParcel.id)
    return resp(paginate(request, q, ser.govt_parcel))


@router.get("/gis/govt-land/geojson/")
def parcels_geojson(request: Request, user: Officer, db: DB):
    """GeoJSON FeatureCollection; optional ?bbox=minx,miny,maxx,maxy for map viewport loading."""
    p = request.query_params
    q = apply_filters(db.query(m.GovtLandParcel).filter(m.GovtLandParcel.active == True), m.GovtLandParcel, p, ("agency", "ward", "village"))  # noqa: E712
    q = apply_search(q, p, [m.GovtLandParcel.name, m.GovtLandParcel.khasra_no, m.GovtLandParcel.village, m.GovtLandParcel.land_use])
    bbox = p.get("bbox")
    minx = miny = maxx = maxy = None
    if bbox:
        try:
            minx, miny, maxx, maxy = [float(x) for x in bbox.split(",")]
        except ValueError:
            return resp({"detail": "bad bbox"}, 400)
    rows = q.order_by(m.GovtLandParcel.id).all()
    ids = [r.id for r in rows]
    cases_by_parcel: dict = {}
    if ids:
        for c in db.query(m.ViolationCase).filter(m.ViolationCase.govt_parcel_id.in_(ids)).all():
            cases_by_parcel.setdefault(c.govt_parcel_id, []).append({"id": str(c.id), "case_no": c.case_no, "status": c.status, "address": c.address_line, "sealed": c.sealed,
                                                                     "stop_work": c.stop_work_issued, "litigation": c.litigation_status, "updated_at": c.updated_at})
    feats = []
    for r in rows:
        b = r.bbox or []
        if bbox and len(b) == 4 and (b[2] < minx or b[0] > maxx or b[3] < miny or b[1] > maxy):
            continue
        cs = cases_by_parcel.get(r.id, [])
        open_cs = [x for x in cs if x["status"] not in ("CLOSED", "DROPPED", "REGULARISED")]
        feats.append({"type": "Feature", "id": r.id, "geometry": r.geometry,
                      "properties": {"id": r.id, "name": r.name, "agency": r.agency, "land_use": r.land_use, "village": r.village, "khasra_no": r.khasra_no, "area_sqm": r.area_sqm,
                                     "layer_key": r.layer_key, "case_count": len(cs), "open_case_count": len(open_cs), "cases": cs[:20]}})
    return resp({"type": "FeatureCollection", "features": feats})


def _apply_parcel(db, p: m.GovtLandParcel, d: dict):
    for k, v in d.items():
        if k == "ward":
            p.ward_id = v
        elif k == "agency":
            if v not in m.AGENCY_LABELS:
                raise WorkflowError(f'"{v}" is not a valid choice.')
            p.agency = v
        else:
            setattr(p, k, v)
    if "geometry" in d and p.geometry:
        p.bbox = geojson_bbox(p.geometry)


@router.post("/gis/govt-land/", status_code=201)
def parcel_create(body: s.GovtParcelIn, user: Officer, db: DB):
    check_perm(db, user, "LAND_LAYERS_MANAGE")
    d = body.model_dump(exclude_unset=True)
    if not d.get("geometry"):
        raise WorkflowError("geometry: This field is required.")
    p = m.GovtLandParcel(geometry=d["geometry"], properties=d.get("properties") or {})
    _apply_parcel(db, p, d)
    db.add(p)
    db.flush()
    return resp(ser.govt_parcel(p), 201)


@router.get("/gis/govt-land/{pk}/")
def parcel_detail(pk: int, user: Officer, db: DB):
    p = db.get(m.GovtLandParcel, pk)
    if not p:
        raise HTTPException(404, "Not found.")
    return resp(ser.govt_parcel(p))


@router.patch("/gis/govt-land/{pk}/")
@router.put("/gis/govt-land/{pk}/")
def parcel_update(pk: int, body: s.GovtParcelIn, user: Officer, db: DB):
    check_perm(db, user, "LAND_LAYERS_MANAGE")
    p = db.get(m.GovtLandParcel, pk)
    if not p:
        raise HTTPException(404, "Not found.")
    _apply_parcel(db, p, body.model_dump(exclude_unset=True))
    db.flush()
    return resp(ser.govt_parcel(p))


@router.delete("/gis/govt-land/{pk}/", status_code=204)
def parcel_delete(pk: int, user: Officer, db: DB):
    check_perm(db, user, "LAND_LAYERS_MANAGE")
    p = db.get(m.GovtLandParcel, pk)
    if not p:
        raise HTTPException(404, "Not found.")
    db.delete(p)
    db.flush()
    return resp(None, 204)


# ---------------------------------------------------------------- land layer uploads (GIS lab)
@router.get("/gis/land-layers/")
def layers(request: Request, user: Officer, db: DB):
    q = apply_filters(db.query(m.LandLayerUpload), m.LandLayerUpload, request.query_params, ("agency", "active", "layer_key")).order_by(m.LandLayerUpload.created_at.desc(), m.LandLayerUpload.id.desc())
    return resp(paginate(request, q, lambda o: ser.land_layer(db, o)))


@router.post("/gis/land-layers/", status_code=201)
def layer_create(request: Request, user: Officer, db: DB, source_file: UploadFile = File(...), name: str = Form(...), layer_key: str = Form(""), agency: str = Form(...),
                 source: str = Form(""), survey_date: str | None = Form(None), remarks: str = Form(""), order_reference: str = Form("")):
    """Upload a government-land layer (GeoJSON / KML / KMZ / zipped shapefile, WGS84). Re-uploading with the same
    `layer_key` creates a new version and retires the old parcels."""
    check_perm(db, user, "LAND_LAYERS_MANAGE")
    if agency not in m.AGENCY_LABELS:
        raise WorkflowError(f'agency: "{agency}" is not a valid choice.')
    data = source_file.file.read()
    fname = source_file.filename or "layer"
    up = m.LandLayerUpload(name=name, layer_key=layer_key or "", agency=agency, source=source or "", remarks=remarks or "",
                           survey_date=date.fromisoformat(survey_date) if survey_date else None, uploaded_by=user,
                           source_file=storage.save_bytes(storage.dated_path("bvms/land-layers", fname), data))
    db.add(up)
    db.flush()
    try:
        with db.begin_nested():
            import_layer(db, up, data, fname)
            if up.feature_count == 0:
                raise WorkflowError("No polygon features found in the file (check the CRS is EPSG:4326 and geometries are polygons)")
    except WorkflowError:
        db.delete(up)
        db.flush()
        raise
    except Exception as exc:
        db.delete(up)
        db.flush()
        raise WorkflowError(f"Layer could not be imported: {exc}")
    access.log_admin(db, user, "LAND_LAYER_UPLOAD", "LandLayerUpload", up.id, after={"layer_key": up.layer_key, "version": up.version, "features": up.feature_count, "skipped": up.skipped_count, "format": up.file_format},
                     order_reference=order_reference or "", request=request)
    return resp(ser.land_layer(db, up), 201)


@router.get("/gis/land-layers/{pk}/")
def layer_detail(pk: int, user: Officer, db: DB):
    up = db.get(m.LandLayerUpload, pk)
    if not up:
        raise HTTPException(404, "Not found.")
    return resp(ser.land_layer(db, up))


@router.patch("/gis/land-layers/{pk}/")
def layer_update(pk: int, body: dict, user: Officer, db: DB):
    check_perm(db, user, "LAND_LAYERS_MANAGE")
    up = db.get(m.LandLayerUpload, pk)
    if not up:
        raise HTTPException(404, "Not found.")
    for k in ("name", "layer_key", "agency", "source", "remarks"):
        if k in body and body[k] is not None:
            setattr(up, k, str(body[k]))
    if "survey_date" in body:
        up.survey_date = date.fromisoformat(body["survey_date"]) if body["survey_date"] else None
    db.flush()
    return resp(ser.land_layer(db, up))


@router.delete("/gis/land-layers/{pk}/", status_code=204)
def layer_retire(pk: int, request: Request, user: Officer, db: DB):
    """Retire a layer version (parcels become inactive); nothing is physically deleted."""
    check_perm(db, user, "LAND_LAYERS_MANAGE")
    up = db.get(m.LandLayerUpload, pk)
    if not up:
        raise HTTPException(404, "Not found.")
    up.active = False
    for p in db.query(m.GovtLandParcel).filter(m.GovtLandParcel.layer_upload_id == up.id):
        p.active = False
    db.flush()
    access.log_admin(db, user, "LAND_LAYER_RETIRE", "LandLayerUpload", up.id, request=request)
    return resp(None, 204)


@router.post("/gis/land-layers/{pk}/reactivate/")
def layer_reactivate(pk: int, user: Officer, db: DB):
    check_perm(db, user, "LAND_LAYERS_MANAGE")
    up = db.get(m.LandLayerUpload, pk)
    if not up:
        raise HTTPException(404, "Not found.")
    for other in db.query(m.LandLayerUpload).filter(m.LandLayerUpload.layer_key == up.layer_key, m.LandLayerUpload.active == True, m.LandLayerUpload.id != up.id):  # noqa: E712
        other.active = False
    for p in db.query(m.GovtLandParcel).filter(m.GovtLandParcel.layer_key == up.layer_key):
        p.active = False
    up.active = True
    for p in db.query(m.GovtLandParcel).filter(m.GovtLandParcel.layer_upload_id == up.id):
        p.active = True
    db.flush()
    return resp(ser.land_layer(db, up))
