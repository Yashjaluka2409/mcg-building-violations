"""Masters: zones, divisions, wards, violation types, legal sections, order types, SLA config.
Read: any officer (no pagination, as before). Write: permission MASTERS_MANAGE."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from app.routers.building_violations._router import SyncRouter
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.core.errors import WorkflowError
from app.models import building_violations as m
from app.schemas.building_violations import outputs as ser
from app.core.http import apply_filters, apply_search, resp
from app.routers.building_violations.deps import DB, Officer, check_perm

router = SyncRouter(prefix="/masters")


def _apply(obj, data: dict):
    mapper = inspect(type(obj))
    cols = {c.name for c in mapper.columns}
    for k, v in (data or {}).items():
        if k in cols:
            setattr(obj, k, v)
        elif k + "_id" in cols:
            setattr(obj, k + "_id", v)
        elif k in ("id",):
            continue
        else:
            raise WorkflowError(f"Unknown field {k!r}")


def _register(name: str, model, serializer, *, filters=(), search=(), order=None, pk_type=int):
    base = f"/{name}"

    @router.get(base + "/", name=f"{name}-list")
    def _list(request: Request, user: Officer, db: DB):
        p = request.query_params
        q = apply_filters(db.query(model), model, p, filters)
        q = apply_search(q, p, [getattr(model, c) for c in search])
        return resp([serializer(x) for x in q.order_by(*(order or [list(inspect(model).primary_key)[0]]))])

    @router.post(base + "/", status_code=201, name=f"{name}-create")
    def _create(body: dict, user: Officer, db: DB):
        check_perm(db, user, "MASTERS_MANAGE")
        obj = model()
        _apply(obj, body)
        db.add(obj)
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise WorkflowError(f"Could not save: {str(e.orig)[:200]}")
        return resp(serializer(obj), 201)

    @router.get(base + "/{pk}/", name=f"{name}-detail")
    def _detail(pk: str, user: Officer, db: DB):
        obj = db.get(model, pk_type(pk) if pk_type is int and pk.isdigit() else pk)
        if not obj:
            raise HTTPException(404, "Not found.")
        return resp(serializer(obj))

    @router.patch(base + "/{pk}/", name=f"{name}-patch")
    @router.put(base + "/{pk}/", name=f"{name}-put")
    def _update(pk: str, body: dict, user: Officer, db: DB):
        check_perm(db, user, "MASTERS_MANAGE")
        obj = db.get(model, pk_type(pk) if pk_type is int and pk.isdigit() else pk)
        if not obj:
            raise HTTPException(404, "Not found.")
        _apply(obj, body)
        db.flush()
        return resp(serializer(obj))

    @router.delete(base + "/{pk}/", status_code=204, name=f"{name}-delete")
    def _delete(pk: str, user: Officer, db: DB):
        check_perm(db, user, "MASTERS_MANAGE")
        obj = db.get(model, pk_type(pk) if pk_type is int and pk.isdigit() else pk)
        if not obj:
            raise HTTPException(404, "Not found.")
        db.delete(obj)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise WorkflowError("Cannot delete: the record is referenced by cases", 400)
        return resp(None, 204)


# geojson / statutes actions must be declared before the "{pk}" routes of their collection
@router.get("/wards/geojson/")
def wards_geojson(user: Officer, db: DB):
    feats = [{"type": "Feature", "geometry": w.boundary, "properties": {"number": w.number, "name": w.name_en, "zone": w.zone.code}}
             for w in db.query(m.Ward).filter(m.Ward.boundary.isnot(None)).order_by(m.Ward.number)]
    return resp({"type": "FeatureCollection", "features": feats})


@router.get("/legal-sections/statutes/")
def statutes(user: Officer, db: DB):
    return resp([{"code": x.code, "title": x.title, "citation": x.citation, "jurisdiction": x.jurisdiction, "primary": x.primary, "sections": len(x.sections)} for x in db.query(m.LegalStatute).order_by(m.LegalStatute.code)])


_register("zones", m.Zone, ser.zone, order=[m.Zone.id])
_register("divisions", m.Division, ser.division, order=[m.Division.id])
_register("wards", m.Ward, ser.ward, filters=("zone", "division"), order=[m.Ward.number])
_register("violation-types", m.ViolationType, ser.violation_type, filters=("category", "severity", "compoundable", "active", "action_path"), search=("code", "title_en", "title_hi", "description"), order=[m.ViolationType.sort_order, m.ViolationType.code], pk_type=str)
_register("legal-sections", m.LegalSection, ser.legal_section, filters=("statute", "kind", "verify"), search=("section", "heading", "text"), order=[m.LegalSection.statute_id, m.LegalSection.id])
_register("order-types", m.OrderType, ser.order_type, filters=("kind", "active"), order=[m.OrderType.code], pk_type=str)
_register("sla", m.SLAConfig, ser.sla_config, order=[m.SLAConfig.id])
