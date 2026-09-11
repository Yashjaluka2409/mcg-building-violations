"""Sanctioned building plans / licences register with bulk upload."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from app.routers.building_violations._router import SyncRouter
from sqlalchemy.exc import IntegrityError

from app.core.errors import WorkflowError
from app.models import building_violations as m
from app.schemas.building_violations import inputs as s
from app.schemas.building_violations import outputs as ser
from app.core.http import apply_filters, apply_ordering, apply_search, csv_response, paginate, read_table_upload, resp
from app.routers.building_violations.deps import DB, Officer, check_perm

router = SyncRouter(prefix="/sanctioned-plans")

COLUMNS = ["plan_no", "pid", "address", "ward_number", "owner_name", "owner_mobile", "plot_area_sqm", "land_use", "building_type", "sanctioned_on", "valid_till",
           "sanction_mode", "permitted_floors", "permitted_ground_coverage_pct", "permitted_far", "permitted_height_m", "setback_front", "setback_rear", "setback_side",
           "licence_no", "licence_holder", "licence_date", "licence_valid_till", "licence_authority", "colony_name", "architect_name", "architect_registration_no",
           "occupation_certificate_no", "occupation_certificate_on", "latitude", "longitude", "status", "remarks"]
EXAMPLE = ["MCG/BP/2026/00001", "GGN012345", "H.No. 123, Sector 14", "19", "Ramesh Kumar", "9811100001", "250.84", "Residential", "Plotted house", "2026-06-12", "2028-06-11",
           "self-certification", "S+3", "66", "2.0", "15", "3", "3", "0", "", "", "", "", "MCG", "", "Ar. P. Mehta", "CA/2010/48211", "", "", "28.4700", "77.0450", "VALID", ""]


def _date(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _get(db, pk):
    o = db.get(m.SanctionedPlan, pk)
    if not o:
        raise HTTPException(404, "Not found.")
    return o


def _apply(db, sp: m.SanctionedPlan, d: dict):
    for k, v in d.items():
        if k == "ward":
            sp.ward_id = v
        elif k == "zone":
            sp.zone_id = v
        else:
            setattr(sp, k, v)


@router.get("/")
def list_plans(request: Request, user: Officer, db: DB):
    check_perm(db, user, "PLANS_VIEW")
    p = request.query_params
    q = apply_filters(db.query(m.SanctionedPlan), m.SanctionedPlan, p, ("ward", "zone", "status", "land_use", "source", "licence_authority"))
    q = apply_search(q, p, [m.SanctionedPlan.plan_no, m.SanctionedPlan.pid, m.SanctionedPlan.owner_name, m.SanctionedPlan.address, m.SanctionedPlan.licence_no, m.SanctionedPlan.licence_holder, m.SanctionedPlan.colony_name])
    q = apply_ordering(q, p, {k: getattr(m.SanctionedPlan, k) for k in ("sanctioned_on", "valid_till", "created_at")}, [m.SanctionedPlan.id.desc()])
    return resp(paginate(request, q, lambda x: ser.sanctioned_plan(x, request)))


@router.get("/by-pid/{pid}/")
def by_pid(pid: str, request: Request, user: Officer, db: DB):
    check_perm(db, user, "PLANS_VIEW")
    return resp([ser.sanctioned_plan(x, request) for x in db.query(m.SanctionedPlan).filter(m.SanctionedPlan.pid == pid).order_by(m.SanctionedPlan.id.desc())])


@router.get("/template/")
def template(user: Officer, db: DB):
    check_perm(db, user, "PLANS_VIEW")
    return csv_response("sanctioned_plans_template.csv", COLUMNS, [], example=EXAMPLE)


@router.post("/bulk_upload/")
def bulk_upload(request: Request, user: Officer, db: DB, file: UploadFile = File(...)):
    check_perm(db, user, "PLANS_MANAGE")
    rows = read_table_upload(file.filename or "", file.file.read())
    created = updated = 0
    errors = []
    for i, r in enumerate(rows, start=2):
        plan_no = str(r.get("plan_no") or "").strip()
        if not plan_no:
            errors.append({"row": i, "error": "plan_no missing"})
            continue
        try:
            ward = db.query(m.Ward).filter(m.Ward.number == int(r["ward_number"])).first() if r.get("ward_number") not in (None, "") else None
            defaults = dict(
                pid=str(r.get("pid") or "").strip(), address=str(r.get("address") or ""), ward_id=ward.id if ward else None, zone_id=ward.zone_id if ward else None,
                owner_name=str(r.get("owner_name") or ""), owner_mobile=str(r.get("owner_mobile") or "")[:15], plot_area_sqm=_num(r.get("plot_area_sqm")),
                land_use=str(r.get("land_use") or ""), building_type=str(r.get("building_type") or ""), sanctioned_on=_date(r.get("sanctioned_on")) or datetime.today().date(),
                valid_till=_date(r.get("valid_till")), sanction_mode=str(r.get("sanction_mode") or ""), permitted_floors=str(r.get("permitted_floors") or ""),
                permitted_ground_coverage_pct=_num(r.get("permitted_ground_coverage_pct")), permitted_far=_num(r.get("permitted_far")), permitted_height_m=_num(r.get("permitted_height_m")),
                setbacks={k: _num(r.get(f"setback_{k}")) for k in ("front", "rear", "side") if r.get(f"setback_{k}") not in (None, "")},
                licence_no=str(r.get("licence_no") or ""), licence_holder=str(r.get("licence_holder") or ""), licence_date=_date(r.get("licence_date")),
                licence_valid_till=_date(r.get("licence_valid_till")), licence_authority=str(r.get("licence_authority") or ""), colony_name=str(r.get("colony_name") or ""),
                architect_name=str(r.get("architect_name") or ""), architect_registration_no=str(r.get("architect_registration_no") or ""),
                occupation_certificate_no=str(r.get("occupation_certificate_no") or ""), occupation_certificate_on=_date(r.get("occupation_certificate_on")),
                latitude=_num(r.get("latitude")), longitude=_num(r.get("longitude")), status=str(r.get("status") or "VALID"), remarks=str(r.get("remarks") or ""),
                source="BULK_UPLOAD", created_by_id=user.id)
            with db.begin_nested():
                sp = db.query(m.SanctionedPlan).filter(m.SanctionedPlan.plan_no == plan_no).first()
                was_created = sp is None
                if was_created:
                    sp = m.SanctionedPlan(plan_no=plan_no)
                    db.add(sp)
                for k, v in defaults.items():
                    setattr(sp, k, v)
                db.flush()
            created += int(was_created)
            updated += int(not was_created)
        except Exception as exc:
            errors.append({"row": i, "error": str(exc)[:200]})
    return resp({"created": created, "updated": updated, "errors": errors})


@router.post("/", status_code=201)
def create_plan(body: s.SanctionedPlanIn, request: Request, user: Officer, db: DB):
    check_perm(db, user, "PLANS_MANAGE")
    d = body.model_dump(exclude_unset=True)
    missing = [k for k in ("plan_no", "address", "owner_name", "sanctioned_on") if not d.get(k)]
    if missing:
        raise WorkflowError(f"{', '.join(missing)}: This field is required.")
    sp = m.SanctionedPlan(created_by_id=user.id, source="MANUAL", setbacks={})
    _apply(db, sp, d)
    db.add(sp)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise WorkflowError("sanctioned plan with this plan_no already exists.")
    return resp(ser.sanctioned_plan(sp, request), 201)


@router.get("/{pk}/")
def plan_detail(pk: int, request: Request, user: Officer, db: DB):
    check_perm(db, user, "PLANS_VIEW")
    return resp(ser.sanctioned_plan(_get(db, pk), request))


@router.patch("/{pk}/")
@router.put("/{pk}/")
def plan_update(pk: int, body: s.SanctionedPlanIn, request: Request, user: Officer, db: DB):
    check_perm(db, user, "PLANS_MANAGE")
    sp = _get(db, pk)
    _apply(db, sp, body.model_dump(exclude_unset=True))
    db.flush()
    return resp(ser.sanctioned_plan(sp, request))


@router.delete("/{pk}/", status_code=204)
def plan_delete(pk: int, user: Officer, db: DB):
    check_perm(db, user, "PLANS_MANAGE")
    sp = _get(db, pk)
    db.delete(sp)
    db.flush()
    return resp(None, 204)
