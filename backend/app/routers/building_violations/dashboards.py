"""MIS dashboards. All endpoints accept ?zone=&ward=&from=&to= (dates) and honour the user's jurisdiction."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Request
from app.routers.building_violations._router import SyncRouter
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import selectinload

from app.core.timeutil import localtime, now
from app.models import building_violations as m
from app.services.building_violations import access
from app.core.http import resp
from app.routers.building_violations.deps import DB, Officer, check_perm
from app.repositories.building_violations import dashboard_criteria
from app.services.building_violations import hierarchy as H

router = SyncRouter(prefix="/dashboards")

OPEN_EXCLUDE = ["CLOSED", "DROPPED", "REGULARISED"]
STAGE_ORDER = ["DRAFT", "PENDING_AE", "RETURNED_TO_JE", "PENDING_JC", "SCN_ISSUED", "SCN_SERVED", "RESPONSE_PENDING_AE", "RESPONSE_PENDING_JC", "RESPONSE_RECEIVED", "NO_RESPONSE",
               "HEARING_SCHEDULED", "ORDER_ISSUED", "ORDER_SERVED", "APPEAL_STAY", "EXECUTION_DUE", "COMPLIED", "EXECUTED", "CLOSED", "DROPPED", "REGULARISED"]
C = m.ViolationCase


def _crit(request, user, db):
    check_perm(db, user, "DASHBOARD_VIEW")
    return dashboard_criteria(db, user, request.query_params)


def _cnt(db, *f):
    return db.query(func.count(C.id)).filter(*f).scalar() or 0


def _joined_cnt(db, model, crit, *f):
    return db.query(func.count(model.id)).join(C, model.case_id == C.id).filter(*crit, *f).scalar() or 0


@router.get("/summary/")
def summary(request: Request, user: Officer, db: DB):
    crit = _crit(request, user, db)
    t = now()
    d30 = t - timedelta(days=30)
    N, E, A, B, T, L = m.Notice, m.ExecutionRecord, m.Appeal, m.BranchReferral, m.InspectionTask, m.LocationIntegrityCheck
    open_ = [C.status.notin_(OPEN_EXCLUDE)]
    tq = lambda *f: db.query(func.count(T.id)).filter(*f).scalar() or 0  # noqa: E731
    lq = lambda *f: db.query(func.count(L.id)).filter(*f).scalar() or 0  # noqa: E731
    return resp({
        "cases_total": _cnt(db, *crit), "cases_open": _cnt(db, *crit, *open_), "cases_new_30d": _cnt(db, *crit, C.created_at >= d30),
        "govt_land_cases": _cnt(db, *crit, C.land_type.in_(["GOVT_MCG", "GOVT_STATE"])),
        "pending_ae": _cnt(db, *crit, C.status.in_(["PENDING_AE", "RESPONSE_PENDING_AE"])),
        "pending_jc": _cnt(db, *crit, C.status.in_(["PENDING_JC", "RESPONSE_PENDING_JC", "RESPONSE_RECEIVED", "NO_RESPONSE", "HEARING_SCHEDULED"])),
        "scn_issued": _joined_cnt(db, N, crit, N.kind == "NOTICE"), "scn_pending_service": _cnt(db, *crit, C.status == "SCN_ISSUED"),
        "responses_awaited": _cnt(db, *crit, C.status == "SCN_SERVED"), "no_response": _cnt(db, *crit, C.status == "NO_RESPONSE"),
        "stop_work_orders": _joined_cnt(db, N, crit, N.order_type_id == "STOP_WORK_262"), "sealing_orders": _joined_cnt(db, N, crit, N.order_type_id.in_(["SEALING_263A", "RESEALING_263A"])),
        "demolition_orders": _joined_cnt(db, N, crit, N.order_type_id.in_(["DEMOLITION_ORDER_261", "EVICTION_DEMOLITION_ORDER_408A", "DEMOLITION_ORDER_284"])),
        "orders_pending_service": _cnt(db, *crit, C.status == "ORDER_ISSUED"), "compliance_running": _cnt(db, *crit, C.status == "ORDER_SERVED"),
        "execution_due": _cnt(db, *crit, C.status == "EXECUTION_DUE"), "stayed": _cnt(db, *crit, C.status == "APPEAL_STAY"),
        "demolished": _joined_cnt(db, E, crit, E.action.in_(["DEMOLITION", "PARTIAL_DEMOLITION"]), E.mode == "CORPORATION"),
        "sealed": _cnt(db, *crit, C.sealed == True), "self_complied": _cnt(db, *crit, C.status == "COMPLIED") + _joined_cnt(db, E, crit, E.mode == "OWNER_SELF"),  # noqa: E712
        "closed": _cnt(db, *crit, C.status == "CLOSED"), "dropped": _cnt(db, *crit, C.status == "DROPPED"), "regularised": _cnt(db, *crit, C.status == "REGULARISED"),
        "sla_breached_open": _cnt(db, *crit, *open_, C.sla_breached == True),  # noqa: E712
        "signature_failed": _joined_cnt(db, N, crit, N.signature_status == "FAILED"),
        "sms_failed": db.query(func.count(m.NoticeDispatch.id)).join(N, m.NoticeDispatch.notice_id == N.id).join(C, N.case_id == C.id).filter(*crit, m.NoticeDispatch.status == "FAILED").scalar() or 0,
        "demolition_cost_inr": float(db.query(func.coalesce(func.sum(C.demolition_cost_inr), 0)).filter(*crit).scalar() or 0),
        "litigation_pending": _cnt(db, *crit, C.litigation_status == "APPEAL_PENDING"),
        "stayed_high_court": _cnt(db, *crit, C.litigation_status == "STAYED", C.litigation_authority == "HIGH_COURT"),
        "stayed_supreme_court": _cnt(db, *crit, C.litigation_status == "STAYED", C.litigation_authority == "SUPREME_COURT"),
        "stayed_divisional_commissioner": _cnt(db, *crit, C.litigation_status == "STAYED", C.litigation_authority == "DIVISIONAL_COMMISSIONER"),
        "stays_expiring_7d": _joined_cnt(db, A, crit, A.status == "STAYED", A.stay_until.isnot(None), A.stay_until <= (t + timedelta(days=7)).date()),
        "referrals_pending": _joined_cnt(db, B, crit, B.status == "PENDING"),
        "tasks_open": tq(T.status.in_(["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"])),
        "tasks_overdue": tq(T.status.in_(["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"]), T.due_at < t),
        "tasks_violation_found": tq(T.status == "VIOLATION_RECORDED"),
        "tasks_no_violation": tq(T.status.in_(["NO_VIOLATION", "NOT_FOUND"])),
        "referrals_overdue": _joined_cnt(db, B, crit, B.status == "PENDING", B.due_at < t),
        "legacy_orders_total": _cnt(db, *crit, C.source == "LEGACY_ORDER"),
        "legacy_orders_open": _cnt(db, *crit, C.source == "LEGACY_ORDER", C.status.in_(["ORDER_ISSUED", "ORDER_SERVED", "EXECUTION_DUE", "APPEAL_STAY"])),
        "integrity_rejected_30d": lq(L.decision == "REJECTED", L.at >= d30),
        "integrity_flagged_30d": lq(L.decision == "FLAGGED", L.at >= d30),
        "integrity_checked_30d": lq(L.at >= d30, L.context != "PRECHECK"),
        "cost_recovery_pending": _cnt(db, *crit, C.cost_recovery_status.in_(["PENDING", "DEMANDED"])),
    })


@router.get("/funnel/")
def funnel(request: Request, user: Officer, db: DB):
    crit = _crit(request, user, db)
    counts = dict(db.query(C.status, func.count(C.id)).filter(*crit).group_by(C.status).all())
    return resp([{"status": st, "label": m.STATUS_LABELS.get(st, st), "count": counts.get(st, 0)} for st in STAGE_ORDER])


@router.get("/by-area/")
def by_area(request: Request, user: Officer, db: DB):
    crit = _crit(request, user, db)
    by = request.query_params.get("by", "zone")
    if by == "ward":
        key, join = m.Ward.number, (m.Ward, C.ward_id == m.Ward.id)
    else:
        key, join = m.Zone.code, (m.Zone, C.zone_id == m.Zone.id)
    rows = (db.query(key.label("key"), func.count(C.id).label("total"),
                     func.count(case((C.status.notin_(OPEN_EXCLUDE), C.id))).label("open"),
                     func.count(case((C.land_type.in_(["GOVT_MCG", "GOVT_STATE"]), C.id))).label("govt"),
                     func.count(case((C.status.in_(["EXECUTED", "COMPLIED", "CLOSED"]), C.id))).label("executed"),
                     func.count(case((and_(C.sla_breached == True, C.status.notin_(OPEN_EXCLUDE)), C.id))).label("breached"))  # noqa: E712
            .outerjoin(*join).filter(*crit).group_by(key).order_by(key).all())
    scn = dict(db.query(key, func.count(func.distinct(m.Notice.id))).select_from(C).outerjoin(*join).join(m.Notice, m.Notice.case_id == C.id).filter(*crit, m.Notice.kind == "NOTICE").group_by(key).all())
    orders = dict(db.query(key, func.count(func.distinct(m.Notice.id))).select_from(C).outerjoin(*join).join(m.Notice, m.Notice.case_id == C.id).filter(*crit, m.Notice.is_final_order == True).group_by(key).all())  # noqa: E712
    return resp([{"key": r.key, "total": r.total, "open": r.open, "govt": r.govt, "scn": scn.get(r.key, 0), "orders": orders.get(r.key, 0), "executed": r.executed, "breached": r.breached} for r in rows])


@router.get("/violation-mix/")
def violation_mix(request: Request, user: Officer, db: DB):
    crit = _crit(request, user, db)
    CV, VT = m.CaseViolation, m.ViolationType
    rows = (db.query(VT.code, VT.title_en, VT.category, func.count(CV.id)).select_from(CV).join(C, CV.case_id == C.id).join(VT, CV.violation_type_id == VT.code)
            .filter(*crit).group_by(VT.code, VT.title_en, VT.category).order_by(func.count(CV.id).desc()).all())
    cats = (db.query(VT.category, func.count(CV.id)).select_from(CV).join(C, CV.case_id == C.id).join(VT, CV.violation_type_id == VT.code)
            .filter(*crit).group_by(VT.category).order_by(func.count(CV.id).desc()).all())
    land = db.query(C.land_type, func.count(C.id)).filter(*crit).group_by(C.land_type).all()
    return resp({"by_type": [{"code": c, "title": t, "category": cat, "count": n} for c, t, cat, n in rows],
                 "by_category": [{"category": cat, "count": n} for cat, n in cats],
                 "by_land_type": [{"land_type": lt, "count": n} for lt, n in land]})


@router.get("/ageing/")
def ageing(request: Request, user: Officer, db: DB):
    crit = _crit(request, user, db)
    t = now()
    buckets = {"0-7": 0, "8-15": 0, "16-30": 0, "31-60": 0, "61-90": 0, ">90": 0}
    by_stage: dict = {}
    for st, changed, created in db.query(C.status, C.status_changed_at, C.created_at).filter(*crit, C.status.notin_(OPEN_EXCLUDE)).all():
        age = (t - created).days
        b = "0-7" if age <= 7 else "8-15" if age <= 15 else "16-30" if age <= 30 else "31-60" if age <= 60 else "61-90" if age <= 90 else ">90"
        buckets[b] += 1
        by_stage.setdefault(st, []).append((t - changed).days)
    return resp({"buckets": [{"bucket": k, "count": v} for k, v in buckets.items()],
                 "avg_days_in_stage": [{"status": k, "avg_days": round(sum(v) / len(v), 1), "count": len(v)} for k, v in by_stage.items()]})


@router.get("/sla/")
def sla(request: Request, user: Officer, db: DB):
    crit = _crit(request, user, db)
    t = now()
    rows = (db.query(C.current_owner_role, func.count(C.id).label("total"), func.count(case((C.sla_breached == True, C.id))).label("breached"), func.count(case((C.stage_due_at < t, C.id))).label("overdue"))  # noqa: E712
            .filter(*crit, C.status.notin_(OPEN_EXCLUDE)).group_by(C.current_owner_role).all())

    def avg_hours(a, b):
        pairs = db.query(a, b).filter(*crit, a.isnot(None), b.isnot(None)).all()
        if not pairs:
            return None
        secs = [(y - x).total_seconds() for x, y in pairs]
        return round(sum(secs) / len(secs) / 3600, 1)
    return resp({"by_owner_role": [{"current_owner_role": r[0], "total": r.total, "breached": r.breached, "overdue": r.overdue} for r in rows], "avg_hours": {
        "je_submit_to_ae_forward": avg_hours(C.submitted_at, C.ae_forwarded_at), "ae_forward_to_scn": avg_hours(C.ae_forwarded_at, C.scn_issued_at),
        "scn_issue_to_service": avg_hours(C.scn_issued_at, C.scn_served_at), "scn_service_to_decision": avg_hours(C.scn_served_at, C.decided_at),
        "order_issue_to_service": avg_hours(C.order_issued_at, C.order_served_at), "order_service_to_execution": avg_hours(C.order_served_at, C.executed_at),
        "inspection_to_closure": avg_hours(C.inspected_at, C.closed_at)}})


@router.get("/officers/")
def officers(request: Request, user: Officer, db: DB):
    crit = _crit(request, user, db)
    U = m.User

    def fmt(rows):
        return [{"user_id": r[0], "name": f"{r[1] or ''} {r[2] or ''}".strip(), **r[3]} for r in rows]

    je_rows = (db.query(U.id, U.first_name, U.last_name, func.count(C.id), func.count(case((C.status != "DRAFT", C.id))), func.count(case((and_(C.sla_breached == True, C.current_owner_role.in_(H.slot_roles(db, "REPORTER"))), C.id))))  # noqa: E712
               .select_from(C).join(U, C.reported_by_id == U.id).filter(*crit).group_by(U.id, U.first_name, U.last_name).all())
    returned = dict(db.query(C.reported_by_id, func.count(m.CaseEvent.id)).join(m.CaseEvent, m.CaseEvent.case_id == C.id).filter(*crit, m.CaseEvent.action == "AE_RETURN").group_by(C.reported_by_id).all())
    je = fmt([(r[0], r[1], r[2], {"cases": r[3], "submitted": r[4], "returned": returned.get(r[0], 0), "overdue": r[5]}) for r in je_rows])
    ae_rows = (db.query(U.id, U.first_name, U.last_name, func.count(C.id), func.count(case((C.status.in_(["PENDING_AE", "RESPONSE_PENDING_AE"]), C.id))), func.count(case((and_(C.sla_breached == True, C.current_owner_role.in_(H.slot_roles(db, "REVIEWER"))), C.id))))  # noqa: E712
               .select_from(C).join(U, C.assigned_ae_id == U.id).filter(*crit).group_by(U.id, U.first_name, U.last_name).all())
    ae = fmt([(r[0], r[1], r[2], {"cases": r[3], "pending": r[4], "overdue": r[5]}) for r in ae_rows])
    jc_rows = (db.query(U.id, U.first_name, U.last_name, func.count(C.id), func.count(case((and_(C.current_owner_role.in_(H.slot_roles(db, "AUTHORITY")), C.status.notin_(OPEN_EXCLUDE)), C.id))), func.count(case((and_(C.sla_breached == True, C.current_owner_role.in_(H.slot_roles(db, "AUTHORITY"))), C.id))))  # noqa: E712
               .select_from(C).join(U, C.assigned_jc_id == U.id).filter(*crit).group_by(U.id, U.first_name, U.last_name).all())
    notices = dict(db.query(C.assigned_jc_id, func.count(m.Notice.id)).join(m.Notice, m.Notice.case_id == C.id).filter(*crit, C.assigned_jc_id.isnot(None)).group_by(C.assigned_jc_id).all())
    orders = dict(db.query(C.assigned_jc_id, func.count(m.Notice.id)).join(m.Notice, m.Notice.case_id == C.id).filter(*crit, C.assigned_jc_id.isnot(None), m.Notice.is_final_order == True).group_by(C.assigned_jc_id).all())  # noqa: E712
    jc = fmt([(r[0], r[1], r[2], {"cases": r[3], "pending": r[4], "notices": notices.get(r[0], 0), "orders": orders.get(r[0], 0), "overdue": r[5]}) for r in jc_rows])
    return resp({"je": je, "ae": ae, "jc": jc})


def _period(dt, gran):
    d = localtime(dt).date()
    if gran == "week":
        return (d - timedelta(days=d.weekday())).isoformat()
    return d.replace(day=1).isoformat()


@router.get("/trends/")
def trends(request: Request, user: Officer, db: DB):
    crit = _crit(request, user, db)
    gran = request.query_params.get("granularity", "month")
    series: dict = {}

    def bump(k, name, n=1):
        if not k:
            return
        series.setdefault(k, {"period": k})
        series[k][name] = series[k].get(name, 0) + n

    for (created,) in db.query(C.created_at).filter(*crit).all():
        bump(_period(created, gran), "new_cases")
    for issued, final in db.query(m.Notice.issued_at, m.Notice.is_final_order).join(C, m.Notice.case_id == C.id).filter(*crit).all():
        k = _period(issued, gran)
        bump(k, "notices")
        series[k].setdefault("orders", 0)
        if final:
            series[k]["orders"] += 1
    for ex_on, action in db.query(m.ExecutionRecord.executed_on, m.ExecutionRecord.action).join(C, m.ExecutionRecord.case_id == C.id).filter(*crit).all():
        k = _period(ex_on, gran)
        bump(k, "executions")
        series[k].setdefault("demolitions", 0)
        series[k].setdefault("sealings", 0)
        if action in ("DEMOLITION", "PARTIAL_DEMOLITION"):
            series[k]["demolitions"] += 1
        if action == "SEALING":
            series[k]["sealings"] += 1
    for (closed,) in db.query(C.closed_at).filter(*crit, C.closed_at.isnot(None)).all():
        bump(_period(closed, gran), "closed")
    return resp(sorted(series.values(), key=lambda x: x["period"]))


@router.get("/map/")
def map_view(request: Request, user: Officer, db: DB):
    """Case pins with status and a short history for pop-ups. ?open=1 open cases only; ?tasks=1 adds planned inspections."""
    crit = _crit(request, user, db)
    p = request.query_params
    q = db.query(C).filter(*crit, C.latitude.isnot(None)).options(selectinload(C.events), selectinload(C.violations))
    if p.get("open") == "1":
        q = q.filter(C.status.notin_(OPEN_EXCLUDE))
    n_hist = int(access.get_setting(db, "map_history_events", 6) or 6)
    feats = []
    for c in q.order_by(C.created_at.desc()).limit(5000):
        hist = [{"at": e.at, "action": e.action, "to": e.to_status, "actor": e.actor_role, "remarks": (e.remarks or "")[:120]} for e in list(c.events)[-n_hist:]]
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(c.longitude), float(c.latitude)]},
                      "properties": {"kind": "case", "id": str(c.id), "case_no": c.case_no, "status": c.status, "status_label": c.get_status_display(), "land_type": c.land_type, "priority": c.priority,
                                     "address": c.address_line, "pid": c.pid, "owner": c.owner_name, "ward": c.ward.number if c.ward else None, "sealed": c.sealed, "stop_work": c.stop_work_issued,
                                     "litigation": c.litigation_status, "stay_until": c.stay_until, "violations": [v.violation_type_id for v in c.violations], "scn_issued_at": c.scn_issued_at,
                                     "order_issued_at": c.order_issued_at, "compliance_due_at": c.compliance_due_at, "executed_at": c.executed_at, "updated_at": c.updated_at, "history": hist}})
    if p.get("tasks") == "1":
        T = m.InspectionTask
        tq = db.query(T).filter(T.latitude.isnot(None))
        if p.get("open") == "1":
            tq = tq.filter(T.status.in_(["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"]))
        for t in tq.order_by(T.id.desc()).limit(3000):
            a = t.assigned_to
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(t.longitude), float(t.latitude)]},
                          "properties": {"kind": "task", "id": t.id, "pid": t.pid, "address": t.address, "status": t.status, "status_label": t.get_status_display(), "category": t.category,
                                         "due_at": t.due_at, "assigned_to": a.bvms_profile.display_name if a is not None and getattr(a, "bvms_profile", None) else None}})
    return resp({"type": "FeatureCollection", "features": feats})


@router.get("/deadlines/")
def deadlines(request: Request, user: Officer, db: DB):
    crit = _crit(request, user, db)
    t = now()
    soon = t + timedelta(days=int(request.query_params.get("days", 7)))
    f = lambda c, dt: {"id": str(c.id), "case_no": c.case_no, "address": c.address_line, "ward": c.ward.number if c.ward else None, "due": dt}  # noqa: E731
    resp_due = db.query(C).filter(*crit, C.status == "SCN_SERVED", C.response_due_at <= soon).order_by(C.response_due_at).limit(100).all()
    comp = db.query(C).filter(*crit, C.status == "ORDER_SERVED", C.compliance_due_at <= soon).order_by(C.compliance_due_at).limit(100).all()
    H, A, B = m.Hearing, m.Appeal, m.BranchReferral
    hearings = db.query(H).join(C, H.case_id == C.id).filter(*crit, H.held_at.is_(None), H.scheduled_at <= soon).order_by(H.scheduled_at).limit(100).all()
    appeals = db.query(A).join(C, A.case_id == C.id).filter(*crit, A.status == "STAYED", A.stay_until.isnot(None), A.stay_until <= soon.date()).limit(100).all()
    court = (db.query(A).join(C, A.case_id == C.id).filter(*crit, A.next_hearing_on.isnot(None), A.next_hearing_on <= soon.date(), A.next_hearing_on >= t.date(),
                                                          A.status.notin_(["DISMISSED", "ALLOWED", "WITHDRAWN", "DISPOSED"])).limit(100).all())
    refs = db.query(B).join(C, B.case_id == C.id).filter(*crit, B.status == "PENDING", B.due_at <= soon).limit(100).all()
    return resp({"responses_due": [f(c, c.response_due_at) for c in resp_due], "compliance_due": [f(c, c.compliance_due_at) for c in comp],
                 "hearings": [{**f(h.case, h.scheduled_at), "venue": h.venue} for h in hearings],
                 "stays_expiring": [{**f(a.case, a.stay_until), "authority": a.get_authority_display()} for a in appeals],
                 "court_dates": [{**f(a.case, a.next_hearing_on), "authority": a.get_authority_display(), "appeal_no": a.appeal_no} for a in court],
                 "referrals_due": [{**f(r.case, r.due_at), "branch": r.branch.name_en} for r in refs]})
