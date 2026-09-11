"""Location-integrity endpoints (anti-GPS-spoofing).

POST /integrity/nonce/     -> {nonce}   single-use nonce the app binds into Play Integrity / App Attest requests
POST /integrity/precheck/  -> check     the app's home screen sends its device signals + current fix; the server
                                        answers PASS / FLAGGED / REJECTED with reasons, without recording evidence
GET  /integrity/checks/    -> list      register of checks (filter ?decision=REJECTED&officer=&context=), for admins /
                                        supervisors; the same data is exported by the "location-integrity" report
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request
from app.routers.building_violations._router import SyncRouter
from sqlalchemy import func

from app.core.timeutil import now
from app.models import building_violations as m
from app.services.building_violations import location_integrity as li
from app.schemas.building_violations import inputs as s
from app.schemas.building_violations import outputs as ser
from app.core.http import apply_filters, paginate, resp
from app.routers.building_violations.deps import DB, Officer, check_perm

router = SyncRouter(prefix="/integrity")
L = m.LocationIntegrityCheck


@router.post("/nonce/")
def nonce(user: Officer, db: DB):
    return resp({"nonce": li.issue_nonce(db, user), "ttl_s": int(li.NONCE_TTL.total_seconds())})


@router.post("/precheck/")
def precheck(body: s.PrecheckIn, request: Request, user: Officer, db: DB):
    """Body: {latitude, longitude, accuracy_m, location_integrity:{...}}. Never raises; returns the decision."""
    chk = li.evaluate(db, user=user, request=request, context="PRECHECK", latitude=body.latitude, longitude=body.longitude, accuracy_m=body.accuracy_m,
                      signals=body.location_integrity, device_id=body.device_id or "", enforce=False)
    out = li.summary(chk)
    out["advice"] = li.ADVICE if chk.decision == "REJECTED" else ""
    return resp(out)


@router.get("/checks/")
def checks(request: Request, user: Officer, db: DB):
    check_perm(db, user, "REPORTS_EXPORT")
    q = apply_filters(db.query(L), L, request.query_params, ("decision", "context", "officer", "case", "task", "platform", "source")).order_by(L.at.desc(), L.id.desc())
    return resp(paginate(request, q, ser.integrity_check))


@router.get("/checks/summary/")
def summary(user: Officer, db: DB):
    """Counts by decision and the most frequent reasons (last 30 days)."""
    check_perm(db, user, "REPORTS_EXPORT")
    since = now() - timedelta(days=30)
    reasons = Counter()
    for r, f in db.query(L.reasons, L.flags).filter(L.at >= since, L.decision.in_(("REJECTED", "FLAGGED"))).all():
        reasons.update(list(r or []) + list(f or []))
    by_officer = Counter()
    for c in db.query(L).filter(L.at >= since, L.decision == "REJECTED").all():
        prof = getattr(c.officer, "bvms_profile", None)
        by_officer[prof.display_name if prof else (c.officer.username if c.officer else "")] += 1
    cnt = lambda d: db.query(func.count(L.id)).filter(L.at >= since, L.decision == d).scalar() or 0  # noqa: E731
    return resp({"rejected": cnt("REJECTED"), "flagged": cnt("FLAGGED"), "passed": cnt("PASS"),
                 "reasons": [{"code": k, "text": li.TEXT.get(k, k), "count": v} for k, v in reasons.most_common(12)],
                 "repeat_offenders": [{"officer": k, "rejections": v} for k, v in by_officer.most_common(10) if k]})


@router.get("/checks/{pk}/")
def check_detail(pk: int, user: Officer, db: DB):
    check_perm(db, user, "REPORTS_EXPORT")
    o = db.get(L, pk)
    if not o:
        raise HTTPException(404, "Not found.")
    return resp(ser.integrity_check(o))
