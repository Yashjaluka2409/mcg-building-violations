"""Administration: branches, workflow rules, settings, role permissions, officer overrides, audit log,
bulk re-assignment. Every write is recorded in AdminAuditLog with the office-order reference."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from app.routers.building_violations._router import SyncRouter
from sqlalchemy import or_

from app.core.errors import WorkflowError
from app.models import building_violations as m
from app.db.util import update_or_create
from app.services.building_violations import access
from app.services.building_violations import hierarchy as H
from app.services.building_violations import workflow as wf
from app.schemas.building_violations import inputs as s
from app.schemas.building_violations import outputs as ser
from app.core.http import resp
from app.routers.building_violations.deps import DB, Officer, check_perm

router = SyncRouter()


# ---------------------------------------------------------------- branches
@router.get("/branches/")
def branches(user: Officer, db: DB):
    return resp([ser.branch(b) for b in db.query(m.Branch).order_by(m.Branch.code)])


@router.post("/branches/", status_code=201)
def branch_create(body: s.BranchIn, request: Request, user: Officer, db: DB):
    check_perm(db, user, "BRANCH_MANAGE")
    d = body.model_dump(exclude_unset=True)
    ref = d.pop("order_reference", "")
    if not d.get("code") or not d.get("name_en"):
        raise WorkflowError("code and name_en are required")
    if db.get(m.Branch, d["code"]):
        raise WorkflowError("branch with this code already exists.")
    b = m.Branch(**{k: v for k, v in d.items() if v is not None})
    db.add(b)
    db.flush()
    access.log_admin(db, user, "BRANCH_CREATE", "Branch", b.code, after=ser.branch(b), order_reference=ref, request=request)
    return resp(ser.branch(b), 201)


@router.get("/branches/{code}/")
def branch_detail(code: str, user: Officer, db: DB):
    b = db.get(m.Branch, code)
    if not b:
        raise HTTPException(404, "Not found.")
    return resp(ser.branch(b))


@router.patch("/branches/{code}/")
@router.put("/branches/{code}/")
def branch_update(code: str, body: s.BranchIn, request: Request, user: Officer, db: DB):
    check_perm(db, user, "BRANCH_MANAGE")
    b = db.get(m.Branch, code)
    if not b:
        raise HTTPException(404, "Not found.")
    d = body.model_dump(exclude_unset=True)
    ref = d.pop("order_reference", "")
    d.pop("code", None)
    before = ser.branch(b)
    for k, v in d.items():
        if v is not None:
            setattr(b, k, v)
    db.flush()
    access.log_admin(db, user, "BRANCH_UPDATE", "Branch", b.code, before=before, after=ser.branch(b), order_reference=ref, request=request)
    return resp(ser.branch(b))


@router.delete("/branches/{code}/", status_code=204)
def branch_delete(code: str, request: Request, user: Officer, db: DB):
    check_perm(db, user, "BRANCH_MANAGE")
    b = db.get(m.Branch, code)
    if not b:
        raise HTTPException(404, "Not found.")
    db.delete(b)
    db.flush()
    access.log_admin(db, user, "BRANCH_DELETE", "Branch", code, request=request)
    return resp(None, 204)


# ---------------------------------------------------------------- workflow rules
def _rules_payload(db):
    access.seed_rules(db)
    matrix: dict = {}
    for r in db.query(m.WorkflowRule).filter(m.WorkflowRule.allowed == True).order_by(m.WorkflowRule.id):  # noqa: E712
        matrix.setdefault(r.status, {}).setdefault(r.role, []).append(r.action)
    return {"statuses": ["*"] + [c[0] for c in m.CaseStatus.choices], "status_labels": {"*": "Any status", **m.STATUS_LABELS},
            "roles": H.role_codes(db), "role_labels": H.role_labels(db), "role_short": {c: H.role_short(db, c) for c in H.role_codes(db)}, "actions": access.ALL_ACTIONS, "action_labels": access.ACTION_LABELS,
            "management_roles": list(access.MANAGEMENT_ROLES), "matrix": matrix}


@router.get("/admin/workflow-rules/")
def rules_get(user: Officer, db: DB):
    return resp(_rules_payload(db))


@router.put("/admin/workflow-rules/")
def rules_put(body: dict, request: Request, user: Officer, db: DB):
    if not access.has_perm(db, user, "WORKFLOW_CONFIGURE"):
        return resp({"detail": "Requires permission WORKFLOW_CONFIGURE"}, 403)
    changed = []
    for r in body.get("rules") or []:
        if r.get("action") not in access.ALL_ACTIONS or r.get("role") not in H.role_codes(db, active_only=False) or (r.get("status") != "*" and r.get("status") not in m.STATUS_LABELS):
            return resp({"detail": f"Invalid rule {r}"}, 400)
        obj, _ = update_or_create(db, m.WorkflowRule, defaults={"allowed": bool(r.get("allowed", True)), "updated_by_id": user.id}, status=r["status"], role=r["role"], action=r["action"])
        changed.append({"status": obj.status, "role": obj.role, "action": obj.action, "allowed": obj.allowed})
    access.invalidate()
    access.log_admin(db, user, "RULES_UPDATE", "WorkflowRule", "", after={"changed": changed}, order_reference=body.get("order_reference", ""), remarks=body.get("remarks", ""), request=request)
    return resp(_rules_payload(db))


@router.post("/admin/workflow-rules/")
def rules_reset(request: Request, user: Officer, db: DB, body: dict | None = None):
    if not access.has_perm(db, user, "WORKFLOW_CONFIGURE"):
        return resp({"detail": "Requires permission WORKFLOW_CONFIGURE"}, 403)
    db.query(m.WorkflowRule).delete(synchronize_session=False)
    access.seed_rules(db, force=True)
    access.log_admin(db, user, "RULES_RESET", "WorkflowRule", "", order_reference=(body or {}).get("order_reference", ""), request=request)
    return resp(_rules_payload(db))


# ---------------------------------------------------------------- review hierarchy (roles + stages)
@router.get("/admin/hierarchy/")
def hierarchy_get(user: Officer, db: DB):
    return resp(H.admin_payload(db))


@router.put("/admin/hierarchy/")
def hierarchy_put(body: dict, request: Request, user: Officer, db: DB):
    """Replace the review chain and edit the role catalogue. Body: {stages:[{slot, role, label_en, label_hi}],
    roles:[{code, label_en, label_hi, short_label, kind, active}], order_reference, remarks}."""
    if not access.has_perm(db, user, "WORKFLOW_CONFIGURE"):
        return resp({"detail": "Requires permission WORKFLOW_CONFIGURE"}, 403)
    before = {"stages": [s.as_dict() for s in H.chain(db)], "roles": H.roles(db)}
    H.save(db, stages=body.get("stages") or [], roles_in=body.get("roles") or [], actor=user)
    access.invalidate()
    after = {"stages": [s.as_dict() for s in H.chain(db)], "roles": H.roles(db)}
    access.log_admin(db, user, "HIERARCHY_UPDATE", "ReviewStage", "", before=before, after=after, order_reference=body.get("order_reference", ""), remarks=body.get("remarks", ""), request=request)
    return resp(H.admin_payload(db))


@router.post("/admin/hierarchy/reset/")
def hierarchy_reset(request: Request, user: Officer, db: DB, body: dict | None = None):
    if not access.has_perm(db, user, "WORKFLOW_CONFIGURE"):
        return resp({"detail": "Requires permission WORKFLOW_CONFIGURE"}, 403)
    H.reset(db)
    access.invalidate()
    access.log_admin(db, user, "HIERARCHY_RESET", "ReviewStage", "", order_reference=(body or {}).get("order_reference", ""), request=request)
    return resp(H.admin_payload(db))


# ---------------------------------------------------------------- settings
def _settings_payload(db):
    access.seed_settings(db)
    return [ser.workflow_setting(x) for x in db.query(m.WorkflowSetting).order_by(m.WorkflowSetting.key)]


@router.get("/admin/settings/")
def settings_get(user: Officer, db: DB):
    return resp(_settings_payload(db))


@router.put("/admin/settings/")
def settings_put(body: dict, request: Request, user: Officer, db: DB):
    if not access.has_perm(db, user, "WORKFLOW_CONFIGURE"):
        return resp({"detail": "Requires permission WORKFLOW_CONFIGURE"}, 403)
    access.seed_settings(db)
    before, after = {}, {}
    for key, value in (body.get("values") or {}).items():
        row = db.get(m.WorkflowSetting, key)
        if not row:
            return resp({"detail": f"Unknown setting {key}"}, 400)
        if row.value_type == "bool":
            value = bool(value)
        elif row.value_type == "int":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return resp({"detail": f"{key} must be an integer"}, 400)
        before[key], after[key] = row.value, value
        row.value, row.updated_by_id = value, user.id
    db.flush()
    access.invalidate()
    access.log_admin(db, user, "SETTING_UPDATE", "WorkflowSetting", "", before=before, after=after, order_reference=body.get("order_reference", ""), request=request)
    return resp(_settings_payload(db))


# ---------------------------------------------------------------- permissions
def _perms_payload(db):
    access.seed_permissions(db)
    matrix: dict = {}
    for r in db.query(m.RolePermission).filter(m.RolePermission.allowed == True).order_by(m.RolePermission.id):  # noqa: E712
        matrix.setdefault(r.role, []).append(r.permission)
    return {"permissions": [{"code": c, "label": l, "group": g, "default_roles": roles} for c, (l, g, roles) in access.PERMISSIONS.items()],
            "roles": H.role_codes(db), "role_labels": H.role_labels(db), "role_short": {c: H.role_short(db, c) for c in H.role_codes(db)}, "management_roles": list(access.MANAGEMENT_ROLES), "matrix": matrix}


@router.get("/admin/permissions/")
def perms_get(user: Officer, db: DB):
    return resp(_perms_payload(db))


@router.put("/admin/permissions/")
def perms_put(body: dict, request: Request, user: Officer, db: DB):
    if not access.has_perm(db, user, "ACCESS_CONFIGURE"):
        return resp({"detail": "Requires permission ACCESS_CONFIGURE"}, 403)
    changed = []
    for g in body.get("grants") or []:
        if g.get("permission") not in access.PERMISSIONS or g.get("role") not in H.role_codes(db, active_only=False):
            return resp({"detail": f"Invalid grant {g}"}, 400)
        if g["role"] in access.MANAGEMENT_ROLES:
            continue
        obj, _ = update_or_create(db, m.RolePermission, defaults={"allowed": bool(g.get("allowed", True)), "updated_by_id": user.id}, role=g["role"], permission=g["permission"])
        changed.append({"role": obj.role, "permission": obj.permission, "allowed": obj.allowed})
    access.invalidate()
    access.log_admin(db, user, "PERMISSIONS_UPDATE", "RolePermission", "", after={"changed": changed}, order_reference=body.get("order_reference", ""), remarks=body.get("remarks", ""), request=request)
    return resp(_perms_payload(db))


# ---------------------------------------------------------------- per-officer overrides
def _overrides_payload(db, prof):
    return {"overrides": [ser.permission_override(o) for o in prof.permission_overrides], "effective": sorted(access.permissions_for(db, prof.user)),
            "role_defaults": sorted(access.role_permissions(db).get(prof.role, set()))}


@router.get("/officers/{pk}/permissions/")
def overrides_get(pk: int, user: Officer, db: DB):
    check_perm(db, user, "ACCESS_CONFIGURE", "OFFICERS_MANAGE")
    prof = db.get(m.OfficerProfile, pk)
    if not prof:
        raise HTTPException(404, "Not found.")
    return resp(_overrides_payload(db, prof))


@router.put("/officers/{pk}/permissions/")
def overrides_put(pk: int, body: dict, request: Request, user: Officer, db: DB):
    check_perm(db, user, "ACCESS_CONFIGURE", "OFFICERS_MANAGE")
    prof = db.get(m.OfficerProfile, pk)
    if not prof:
        raise HTTPException(404, "Not found.")
    before = [{"permission": o.permission, "allowed": o.allowed} for o in prof.permission_overrides]
    seen = set()
    for o in body.get("overrides") or []:
        if o.get("permission") not in access.PERMISSIONS:
            return resp({"detail": f"Unknown permission {o.get('permission')}"}, 400)
        update_or_create(db, m.OfficerPermissionOverride, defaults={"allowed": bool(o.get("allowed", True)), "reason": o.get("reason", ""), "order_reference": body.get("order_reference", ""), "updated_by_id": user.id},
                         profile_id=prof.id, permission=o["permission"])
        seen.add(o["permission"])
    if body.get("replace", True):
        for o in db.query(m.OfficerPermissionOverride).filter(m.OfficerPermissionOverride.profile_id == prof.id, m.OfficerPermissionOverride.permission.notin_(seen) if seen else True):
            db.delete(o)
    db.flush()
    db.expire(prof)
    access.invalidate()
    access.log_admin(db, user, "OFFICER_OVERRIDES_UPDATE", "OfficerProfile", prof.id, before={"overrides": before},
                     after={"overrides": [{"permission": o.permission, "allowed": o.allowed} for o in prof.permission_overrides]}, order_reference=body.get("order_reference", ""), request=request)
    return resp(_overrides_payload(db, prof))


# ---------------------------------------------------------------- audit log
@router.get("/admin/audit-log/")
def audit_log(request: Request, user: Officer, db: DB):
    check_perm(db, user, "AUDIT_VIEW", "WORKFLOW_CONFIGURE", "ACCESS_CONFIGURE", "OFFICERS_MANAGE")
    p = request.query_params
    q = db.query(m.AdminAuditLog).outerjoin(m.User, m.AdminAuditLog.actor_id == m.User.id)
    if p.get("action"):
        q = q.filter(m.AdminAuditLog.action == p["action"])
    if p.get("search"):
        like = f"%{p['search']}%"
        q = q.filter(or_(m.AdminAuditLog.target_id.ilike(like), m.AdminAuditLog.order_reference.ilike(like), m.AdminAuditLog.remarks.ilike(like), m.User.first_name.ilike(like)))
    return resp([ser.admin_audit_log(x) for x in q.order_by(m.AdminAuditLog.at.desc(), m.AdminAuditLog.id.desc()).limit(500)])


# ---------------------------------------------------------------- bulk re-assignment
@router.post("/admin/reassign-cases/")
def bulk_reassign(body: s.BulkReassignIn, request: Request, user: Officer, db: DB):
    """Re-assign many cases at once when jurisdictions change (by explicit ids, or by zone / ward / current officer)."""
    check_perm(db, user, "CASE_REASSIGN")
    d = body.model_dump()
    C = m.ViolationCase
    q = db.query(C)
    if d.get("case_ids"):
        q = q.filter(C.id.in_(d["case_ids"]))
    if d.get("zone"):
        q = q.filter(C.zone_id == d["zone"])
    if d.get("ward"):
        q = q.filter(C.ward_id == d["ward"])
    if d.get("from_user"):
        u = d["from_user"]
        q = q.filter(or_(C.assigned_ae_id == u, C.assigned_jc_id == u, C.reported_by_id == u))
    if d.get("only_open", True):
        q = q.filter(C.status.notin_(["CLOSED", "DROPPED", "REGULARISED"]))
    if not (d.get("case_ids") or d.get("zone") or d.get("ward") or d.get("from_user")):
        return resp({"detail": "Give case_ids, zone, ward or from_user"}, 400)
    users = {}
    for k in ("assigned_ae", "assigned_jc", "reported_by"):
        if d.get(k):
            users[k] = db.get(m.User, d[k])
            if users[k] is None:
                raise WorkflowError(f'Invalid pk "{d[k]}" - object does not exist.')
        else:
            users[k] = None
    n = 0
    for case in q.order_by(C.created_at).limit(2000).all():
        wf.reassign_case(db, case, user, request=request, assigned_ae=users["assigned_ae"], assigned_jc=users["assigned_jc"], reported_by=users["reported_by"], remarks=d.get("remarks", ""), order_reference=d.get("order_reference", ""))
        n += 1
    access.log_admin(db, user, "CASES_REASSIGN", "ViolationCase", "", after={"count": n, "assigned_ae": d.get("assigned_ae"), "assigned_jc": d.get("assigned_jc"), "reported_by": d.get("reported_by"),
                                                                            "filters": {"zone": d.get("zone"), "ward": d.get("ward"), "from_user": d.get("from_user")}},
                     order_reference=d.get("order_reference", ""), remarks=d.get("remarks", ""), request=request)
    return resp({"reassigned": n})
