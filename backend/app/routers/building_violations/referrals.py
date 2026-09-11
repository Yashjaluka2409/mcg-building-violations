"""Branch referrals: list (scoped) and counts. The actions live on the case (refer_branch / respond_branch / close_referral)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from app.routers.building_violations._router import SyncRouter
from sqlalchemy import or_

from app.core.timeutil import now
from app.models import building_violations as m
from app.services.building_violations import access
from app.schemas.building_violations import outputs as ser
from app.core.http import apply_filters, apply_ordering, apply_search, paginate, resp
from app.routers.building_violations.deps import DB, Officer

router = SyncRouter(prefix="/referrals")
R, C = m.BranchReferral, m.ViolationCase


def scoped(db, user, params):
    prof = user.bvms_profile
    q = db.query(R).join(C, R.case_id == C.id)
    if prof.role in access.MANAGEMENT_ROLES or access.has_perm(db, user, "REFERRALS_VIEW_ALL"):
        pass
    elif prof.role == m.Role.BRANCH_OFFICER:
        q = q.filter(or_(R.branch_id == prof.branch_id, R.assigned_to_id == user.id))
    else:
        q = q.filter(or_(R.referred_by_id == user.id, C.assigned_jc_id == user.id, C.assigned_ae_id == user.id, C.reported_by_id == user.id))
    if params.get("inbox") == "1":
        q = q.filter(R.status == "PENDING")
    return q


@router.get("/")
def list_referrals(request: Request, user: Officer, db: DB):
    p = request.query_params
    q = apply_filters(scoped(db, user, p), R, p, ("status", "branch", "case", "hold_case"))
    q = apply_search(q, p, [C.case_no, C.address_line, R.query, R.response])
    q = apply_ordering(q, p, {k: getattr(R, k) for k in ("referred_at", "due_at", "responded_at")}, [R.referred_at.desc()])
    return resp(paginate(request, q, ser.referral))


@router.get("/counts/")
def counts(request: Request, user: Officer, db: DB):
    q = scoped(db, user, request.query_params)
    n = lambda *f: q.filter(*f).order_by(None).count()  # noqa: E731
    return resp({"pending": n(R.status == "PENDING"), "overdue": n(R.status == "PENDING", R.due_at < now()), "responded": n(R.status == "RESPONDED")})


@router.get("/{pk}/")
def referral_detail(pk: int, request: Request, user: Officer, db: DB):
    r = scoped(db, user, request.query_params).filter(R.id == pk).first()
    if not r:
        raise HTTPException(404, "Not found.")
    return resp(ser.referral(r))
