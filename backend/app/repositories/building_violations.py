"""Jurisdiction scoping of cases (who sees which cases). Shared by the case list, notices, dashboards,
reports and the legacy register. Admin-configurable: CASE_VIEW_ALL lifts the filter for any role."""
from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import false, or_
from sqlalchemy.orm import Query, Session, selectinload

from app.core.timeutil import as_date, make_aware_local, now
from app.models import building_violations as m
from app.services.building_violations import access, hierarchy as H

OPEN_EXCLUDE = ["CLOSED", "DROPPED", "REGULARISED"]


def _in(col, ids):
    return col.in_(ids) if ids else false()


def case_criteria(db: Session, user) -> list:
    prof = user.bvms_profile
    role = prof.role
    crole = H.canonical_role(db, role)   # a stage role is scoped like the slot it fills (JE / AE / JC)
    C = m.ViolationCase
    zone_ids = [z.id for z in prof.zones]
    ward_ids = [w.id for w in prof.wards]
    div_ids = [d.id for d in prof.divisions]
    if role in access.MANAGEMENT_ROLES or access.has_perm(db, user, "CASE_VIEW_ALL"):
        return []
    if role == "BRANCH_OFFICER":
        if access.has_perm(db, user, "CASE_VIEW_BRANCH"):
            return [C.referrals.any(or_(m.BranchReferral.branch_id == prof.branch_id, m.BranchReferral.assigned_to_id == user.id))]
        return [false()]
    if crole == "JE":
        return [or_(C.reported_by_id == user.id, _in(C.ward_id, ward_ids), _in(C.zone_id, zone_ids))]
    if crole in ("AE", "XEN"):
        return [or_(C.assigned_ae_id == user.id, _in(C.zone_id, zone_ids), _in(C.division_id, div_ids))]
    if crole == "JC":
        return [or_(C.assigned_jc_id == user.id, _in(C.zone_id, zone_ids))]
    if role == "JC_CLERK":
        parent = prof.parent_profile
        if not parent:
            return [false()]
        return [or_(C.assigned_jc_id == parent.user_id, _in(C.zone_id, [z.id for z in parent.zones]))]
    if role == "FIELD_STAFF":
        return [or_(_in(C.zone_id, zone_ids), _in(C.ward_id, ward_ids))]
    return []


def list_criteria(db: Session, user, params) -> list:
    """Case-list extras: ?mine=1 ?inbox=1 ?overdue=1."""
    C = m.ViolationCase
    role = user.bvms_profile.role
    crit = case_criteria(db, user)
    if params.get("mine") == "1":
        crit.append(or_(C.reported_by_id == user.id, C.assigned_ae_id == user.id, C.assigned_jc_id == user.id))
    if params.get("inbox") == "1":
        crit.append(C.current_owner_role == (role if role != "JC_CLERK" else H.authority_role(db)))
    if params.get("overdue") == "1":
        crit.append(C.stage_due_at < now())
        crit.append(C.status.notin_(OPEN_EXCLUDE))
    return crit


def dashboard_criteria(db: Session, user, params) -> list:
    """Dashboards / reports: jurisdiction + ?zone=&ward=&land_type=&from=&to= (dates)."""
    C = m.ViolationCase
    crit = case_criteria(db, user)
    if params.get("zone"):
        crit.append(C.zone_id == int(params["zone"]))
    if params.get("ward"):
        crit.append(C.ward_id == int(params["ward"]))
    if params.get("land_type"):
        crit.append(C.land_type == params["land_type"])
    if params.get("from"):
        crit.append(C.created_at >= make_aware_local(datetime.combine(as_date(params["from"]), time.min)))
    if params.get("to"):
        crit.append(C.created_at <= make_aware_local(datetime.combine(as_date(params["to"]), time.max)))
    return crit


def scoped_cases(db: Session, user, params=None, *, dashboard: bool = False) -> Query:
    crit = dashboard_criteria(db, user, params or {}) if dashboard else list_criteria(db, user, params or {})
    return db.query(m.ViolationCase).filter(*crit)


def with_list_loads(q: Query) -> Query:
    return q.options(selectinload(m.ViolationCase.violations).joinedload(m.CaseViolation.violation_type), selectinload(m.ViolationCase.media),
                     selectinload(m.ViolationCase.referrals), selectinload(m.ViolationCase.final_order))
