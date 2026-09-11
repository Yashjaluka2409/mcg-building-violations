"""OTP login (standalone mode), JWT refresh, current user, notifications, officer administration.

When BVMS_USE_PLATFORM_AUTH=1 the platform's /auth/otp/* endpoints are used instead and the OTP routes
are simply not mounted (see main.py)."""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request
from app.routers.building_violations._router import SyncRouter
from sqlalchemy import or_

from app.core.config import settings
from app.core.errors import WorkflowError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.core.timeutil import now
from app.models import building_violations as m
from app.db.util import get_or_create, to_uuid
from app.integrations.sms import get_gateway, normalise_mobile
from app.services.building_violations import access
from app.services.building_violations import hierarchy as H
from app.schemas.building_violations import inputs as s
from app.schemas.building_violations import outputs as ser
from app.core.http import apply_filters, apply_search, paginate, resp
from app.routers.building_violations.deps import DB, Officer

router = SyncRouter()
otp_router = SyncRouter()


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


# ---------------------------------------------------------------- OTP login (standalone)
@otp_router.post("/auth/otp/request/")
def otp_request(body: s.OTPRequestIn, db: DB):
    mobile = normalise_mobile(body.mobile)
    if not mobile:
        return resp({"detail": "Enter a valid 10-digit mobile number"}, 400)
    prof = db.query(m.OfficerProfile).filter(m.OfficerProfile.mobile == mobile, m.OfficerProfile.active == True).first()  # noqa: E712
    if not prof:
        return resp({"detail": "This mobile number is not registered as an officer of the Building Violation module"}, 404)
    code = settings.BVMS_OTP_DEMO_CODE if (settings.DEBUG or settings.DEMO_MODE) else f"{secrets.randbelow(10**6):06d}"
    db.add(m.OTPRequest(mobile=mobile, code_hash=_hash(code), expires_at=now() + timedelta(minutes=10)))
    db.flush()
    get_gateway().send(mobile, f"{code} is your OTP for MCG Building Violation System. Valid 10 minutes. - MCGGGN", "")
    return resp({"detail": "OTP sent", "expires_in": 600})


@otp_router.post("/auth/otp/verify/")
def otp_verify(body: s.OTPVerifyIn, db: DB):
    mobile = normalise_mobile(body.mobile)
    otp = (db.query(m.OTPRequest).filter(m.OTPRequest.mobile == mobile, m.OTPRequest.consumed == False, m.OTPRequest.expires_at > now())  # noqa: E712
           .order_by(m.OTPRequest.created_at.desc(), m.OTPRequest.id.desc()).first())
    if not otp or otp.attempts >= 5:
        return resp({"detail": "OTP expired or too many attempts; request a new OTP"}, 400)
    if otp.code_hash != _hash(body.otp.strip()):
        otp.attempts += 1
        db.flush()
        return resp({"detail": "Incorrect OTP"}, 400)
    otp.consumed = True
    prof = db.query(m.OfficerProfile).filter(m.OfficerProfile.mobile == mobile, m.OfficerProfile.active == True).first()  # noqa: E712
    if not prof:
        return resp({"detail": "This mobile number is not registered as an officer of the Building Violation module"}, 404)
    user = prof.user
    user.last_login = now()
    db.flush()
    return resp({"access_token": create_access_token(user.id, [prof.role]), "refresh_token": create_refresh_token(user.id), "user": ser.me(db, user)})


@otp_router.post("/auth/token/refresh/")
def token_refresh(body: s.TokenRefreshIn, db: DB):
    payload = decode_token(body.refresh, "refresh")
    user = db.get(m.User, to_uuid(payload.get("sub") or payload.get("user_id")))
    if not user or not user.is_active:
        raise HTTPException(401, "User not found")
    return resp({"access": create_access_token(user.id)})


# ---------------------------------------------------------------- me
@router.get("/users/me/")
def me(user: Officer, db: DB):
    return resp(ser.me(db, user))


# ---------------------------------------------------------------- notifications
@router.get("/notifications/")
def notifications(request: Request, user: Officer, db: DB):
    q = db.query(m.Notification).filter(m.Notification.user_id == user.id).order_by(m.Notification.created_at.desc(), m.Notification.id.desc())
    return resp(paginate(request, q, ser.notification))


@router.post("/notifications/mark_read/")
def notifications_mark_read(body: s.NotificationsMarkReadIn, user: Officer, db: DB):
    q = db.query(m.Notification).filter(m.Notification.user_id == user.id, m.Notification.read_at.is_(None))
    if body.ids:
        q = q.filter(m.Notification.id.in_(body.ids))
    n = 0
    for row in q.all():
        row.read_at = now()
        n += 1
    db.flush()
    return resp({"updated": n})


@router.get("/notifications/{pk}/")
def notification_detail(pk: int, user: Officer, db: DB):
    row = db.query(m.Notification).filter(m.Notification.user_id == user.id, m.Notification.id == pk).first()
    if not row:
        raise HTTPException(404, "Not found.")
    return resp(ser.notification(row))


# ---------------------------------------------------------------- officers
def _officer_snapshot(p: m.OfficerProfile) -> dict:
    return {"role": p.role, "designation": p.designation, "mobile": p.mobile, "zones": sorted(z.code for z in p.zones), "wards": sorted(w.number for w in p.wards),
            "divisions": sorted(d.code for d in p.divisions), "reports_to": p.reports_to_id, "branch": p.branch_id, "parent_profile": p.parent_profile_id, "active": p.active,
            "delegation_order_no": p.delegation_order_no}


def _officer_query(db):
    return db.query(m.OfficerProfile).join(m.User, m.OfficerProfile.user_id == m.User.id)


@router.get("/officers/")
def officers(request: Request, user: Officer, db: DB):
    p = request.query_params
    q = apply_filters(_officer_query(db), m.OfficerProfile, p, ("role", "active", "zones", "branch"))
    q = apply_search(q, p, [m.User.first_name, m.User.last_name, m.OfficerProfile.mobile, m.OfficerProfile.designation, m.OfficerProfile.employee_code])
    q = q.order_by(m.OfficerProfile.id)
    return resp(paginate(request, q, lambda x: ser.officer_profile(db, x)))


@router.get("/officers/dropdown/")
def officers_dropdown(request: Request, user: Officer, db: DB):
    p = request.query_params
    q = db.query(m.OfficerProfile).filter(m.OfficerProfile.active == True)  # noqa: E712
    if p.get("role"):
        q = q.filter(m.OfficerProfile.role == p["role"])
    if p.get("slot"):        # REPORTER | REVIEWER | AUTHORITY -> officers of the role(s) filling that stage of the hierarchy
        q = q.filter(m.OfficerProfile.role.in_(H.slot_roles(db, p["slot"].upper())))
    if p.get("zone"):
        q = q.filter(or_(m.OfficerProfile.zones.any(m.Zone.id == int(p["zone"])), ~m.OfficerProfile.zones.any()))
    return resp([{"user_id": x.user_id, "name": x.display_name, "role": x.role, "designation": x.designation} for x in q.order_by(m.OfficerProfile.id)])


def _set_m2m(db, prof, d: dict):
    if d.get("zones") is not None:
        prof.zones = db.query(m.Zone).filter(m.Zone.id.in_(d["zones"])).all() if d["zones"] else []
    if d.get("wards") is not None:
        prof.wards = db.query(m.Ward).filter(m.Ward.id.in_(d["wards"])).all() if d["wards"] else []
    if d.get("divisions") is not None:
        prof.divisions = db.query(m.Division).filter(m.Division.id.in_(d["divisions"])).all() if d["divisions"] else []


SCALAR_FIELDS = ("role", "designation", "employee_code", "mobile", "email", "reports_to", "delegation_order_no", "delegation_order_date", "parent_profile", "branch", "active")


def _apply_scalars(db, prof, d: dict, allowed=SCALAR_FIELDS):
    for k in allowed:
        if k not in d:
            continue
        v = d[k]
        if k == "reports_to":
            prof.reports_to_id = v
        elif k == "parent_profile":
            prof.parent_profile_id = v
        elif k == "branch":
            if v and not db.get(m.Branch, v):
                raise WorkflowError(f'Invalid pk "{v}" - object does not exist.')
            prof.branch_id = v or None
        else:
            setattr(prof, k, v if v is not None else ("" if k in ("designation", "employee_code", "email", "delegation_order_no") else v))


@router.post("/officers/", status_code=201)
def officer_create(body: s.OfficerIn, request: Request, user: Officer, db: DB):
    d = body.model_dump(exclude_unset=True)
    me_prof = user.bvms_profile
    if not d.get("role") or not d.get("mobile"):
        raise WorkflowError("role and mobile are required")
    if d["role"] not in H.role_codes(db):
        raise WorkflowError(f'"{d["role"]}" is not a valid choice.')
    parent = None
    if access.has_perm(db, user, "OFFICERS_MANAGE"):
        pass
    elif access.has_perm(db, user, "CLERK_MANAGE") and d["role"] == "JC_CLERK":
        parent = me_prof
    else:
        raise WorkflowError("Only the module administrator can create officer logins (JC may create clerk sub-logins)", 403)
    if d.get("user_id"):
        u = db.get(m.User, d["user_id"])
        if not u:
            raise WorkflowError(f'Invalid pk "{d["user_id"]}" - object does not exist.')
    else:
        username = d.get("username") or d["mobile"]
        u, _ = get_or_create(db, m.User, defaults={"first_name": d.get("first_name", ""), "last_name": d.get("last_name", "")}, username=username)
    if db.query(m.OfficerProfile.id).filter(m.OfficerProfile.user_id == u.id).first():
        raise WorkflowError("officer profile with this user already exists.")
    prof = m.OfficerProfile(user=u, role=d["role"], mobile=d["mobile"], designation=d.get("designation") or "", employee_code=d.get("employee_code") or "", email=d.get("email") or "",
                            delegation_order_no=d.get("delegation_order_no") or "", delegation_order_date=d.get("delegation_order_date"), active=d.get("active", True) if d.get("active") is not None else True)
    db.add(prof)
    db.flush()
    _apply_scalars(db, prof, {k: v for k, v in d.items() if k in ("reports_to", "parent_profile", "branch")})
    if parent is not None:
        prof.parent_profile_id = parent.id
    _set_m2m(db, prof, d)
    db.flush()
    access.invalidate()
    access.log_admin(db, user, "OFFICER_CREATE", "OfficerProfile", prof.id, after=_officer_snapshot(prof), order_reference=d.get("order_reference", ""), request=request)
    db.expire(prof)
    return resp(ser.officer_profile(db, prof), 201)


@router.get("/officers/{pk}/")
def officer_detail(pk: int, user: Officer, db: DB):
    prof = db.get(m.OfficerProfile, pk)
    if not prof:
        raise HTTPException(404, "Not found.")
    return resp(ser.officer_profile(db, prof))


@router.patch("/officers/{pk}/")
@router.put("/officers/{pk}/")
def officer_update(pk: int, body: s.OfficerIn, request: Request, user: Officer, db: DB):
    prof = db.get(m.OfficerProfile, pk)
    if not prof:
        raise HTTPException(404, "Not found.")
    me_prof = user.bvms_profile
    if not access.has_perm(db, user, "OFFICERS_MANAGE") and prof.parent_profile_id != me_prof.id and prof.id != me_prof.id:
        raise WorkflowError("Not allowed to edit this officer", 403)
    d = body.model_dump(exclude_unset=True)
    if prof.id == me_prof.id and not access.has_perm(db, user, "OFFICERS_MANAGE"):
        for k in ("role", "zones", "wards", "divisions", "reports_to", "branch", "active", "delegation_order_no"):
            d.pop(k, None)   # an officer may edit only contact details of own profile
    if d.get("role") and d["role"] not in H.role_codes(db):
        raise WorkflowError(f'"{d["role"]}" is not a valid choice.')
    before = _officer_snapshot(prof)
    _apply_scalars(db, prof, d)
    _set_m2m(db, prof, d)
    db.flush()
    access.invalidate()
    access.log_admin(db, user, "OFFICER_UPDATE", "OfficerProfile", prof.id, before=before, after=_officer_snapshot(prof), order_reference=d.get("order_reference", ""), request=request)
    db.expire(prof)
    return resp(ser.officer_profile(db, prof))


@router.delete("/officers/{pk}/", status_code=204)
def officer_delete(pk: int, request: Request, user: Officer, db: DB):
    if not access.has_perm(db, user, "OFFICERS_MANAGE"):
        raise HTTPException(403, "Requires permission: OFFICERS_MANAGE")
    prof = db.get(m.OfficerProfile, pk)
    if not prof:
        raise HTTPException(404, "Not found.")
    snap = _officer_snapshot(prof)
    db.delete(prof)
    db.flush()
    access.invalidate()
    access.log_admin(db, user, "OFFICER_DELETE", "OfficerProfile", pk, before=snap, request=request)
    return resp(None, 204)
