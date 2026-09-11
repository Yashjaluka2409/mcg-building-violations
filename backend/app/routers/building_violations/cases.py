"""The case API: list/detail + one endpoint per workflow action (same paths as the Django edition)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from app.routers.building_violations._router import SyncRouter
from sqlalchemy import func

from app.core.errors import WorkflowError
from app.core.timeutil import now
from app.models import building_violations as m
from app.db.util import to_uuid
from app.services.building_violations import location_integrity as li
from app.services.building_violations import workflow as wf
from app.services.building_violations import hierarchy as H
from app.services.building_violations.audit import verify_chain
from app.schemas.building_violations import inputs as s
from app.schemas.building_violations import outputs as ser
from app.core.http import apply_filters, apply_ordering, apply_search, paginate, resp
from app.routers.building_violations.deps import DB, Officer, role_of
from app.repositories.building_violations import OPEN_EXCLUDE, list_criteria, with_list_loads

router = SyncRouter(prefix="/cases")

FILTERS = ("status", "zone", "ward", "division", "land_type", "priority", "source", "current_owner_role", "sla_breached", "stop_work_issued", "sealed", "decision", "reported_by", "assigned_ae", "assigned_jc", "litigation_status", "litigation_authority")
SEARCH = lambda: [m.ViolationCase.case_no, m.ViolationCase.pid, m.ViolationCase.address_line, m.ViolationCase.locality, m.ViolationCase.sector, m.ViolationCase.owner_name, m.ViolationCase.occupier_name, m.ViolationCase.builder_name]  # noqa: E731
ORDERING = lambda: {k: getattr(m.ViolationCase, k) for k in ("created_at", "updated_at", "status_changed_at", "stage_due_at", "response_due_at", "compliance_due_at", "inspected_at")}  # noqa: E731


def scoped(db, user, params):
    return db.query(m.ViolationCase).filter(*list_criteria(db, user, params))


def get_case(db, user, pk, params=None) -> m.ViolationCase:
    u = to_uuid(pk)
    case = scoped(db, user, params or {}).filter(m.ViolationCase.id == u).first() if u else None
    if not case:
        raise HTTPException(404, "Not found.")
    return case


def _obj(db, model, pk, label):
    if pk is None:
        return None
    o = db.get(model, pk)
    if o is None:
        raise WorkflowError(f'Invalid pk "{pk}" - object does not exist.')
    return o


def detail(db, case, request, user, status=200):
    db.flush()
    db.expire(case)
    return resp(ser.case_detail(db, case, request, user), status)


# ---------------------------------------------------------------- list / create / detail
@router.get("/")
def list_cases(request: Request, user: Officer, db: DB):
    p = request.query_params
    q = with_list_loads(scoped(db, user, p))
    q = apply_filters(q, m.ViolationCase, p, FILTERS)
    q = apply_search(q, p, SEARCH())
    q = apply_ordering(q, p, ORDERING(), [m.ViolationCase.created_at.desc()])
    return resp(paginate(request, q, lambda c: ser.case_list(c, request)))


@router.get("/counts/")
def counts(request: Request, user: Officer, db: DB):
    """Badge counts for the inbox / home screen."""
    q = scoped(db, user, request.query_params)
    role = role_of(user)
    C = m.ViolationCase
    n = lambda *f: q.filter(*f).order_by(None).count()  # noqa: E731
    return resp({
        "inbox": n(C.current_owner_role == (role if role != "JC_CLERK" else H.authority_role(db)), C.status.notin_(OPEN_EXCLUDE)),
        "drafts": n(C.status == "DRAFT", C.reported_by_id == user.id),
        "to_serve": n(C.status.in_(["SCN_ISSUED", "ORDER_ISSUED"])),
        "execution_due": n(C.status == "EXECUTION_DUE"),
        "overdue": n(C.stage_due_at < now(), C.status.notin_(OPEN_EXCLUDE)),
        "total_open": n(C.status.notin_(OPEN_EXCLUDE)),
    })


def _resolve_case_data(db, d: dict) -> dict:
    d["ward"] = _obj(db, m.Ward, d.get("ward"), "ward")
    d["zone"] = _obj(db, m.Zone, d.get("zone"), "zone")
    d["division"] = _obj(db, m.Division, d.get("division"), "division")
    d["sanctioned_plan"] = _obj(db, m.SanctionedPlan, d.get("sanctioned_plan"), "sanctioned_plan")
    d["task"] = _obj(db, m.InspectionTask, d.get("task"), "task")
    for k in ("pid_snapshot", "measurements"):
        if d.get(k) is None:
            d[k] = {}
    return d


@router.post("/", status_code=201)
def create_case(body: s.CaseCreateIn, request: Request, user: Officer, db: DB):
    d = body.model_dump()
    violations = [v for v in d.pop("violations")]
    media_ids = d.pop("media_ids", None)
    submit = d.pop("submit", False)
    integrity = d.pop("location_integrity", None)
    for v in violations:
        vt = db.get(m.ViolationType, v["code"])
        if not vt or not vt.active:
            raise WorkflowError(f"Unknown violation code {v['code']}")
    d = _resolve_case_data(db, d)
    chk = None
    if d.get("inspector_latitude") is not None and d.get("inspector_longitude") is not None:
        # Anti-spoofing check on the inspector's position (stored even when the case is then refused).
        chk = li.evaluate(db, user=user, request=request, context="CASE_CREATE", latitude=d["inspector_latitude"], longitude=d["inspector_longitude"],
                          accuracy_m=d.get("location_accuracy_m"), signals=integrity, task=d.get("task"))
    case = wf.create_case(db, user, d, violations, request=request, media_ids=media_ids)
    if chk is not None:
        chk.case = case
        db.flush()
    if submit:
        case = wf.submit_to_ae(db, case, user, request=request)
    return detail(db, case, request, user, 201)


@router.get("/{pk}/")
def case_detail(pk: str, request: Request, user: Officer, db: DB):
    return resp(ser.case_detail(db, get_case(db, user, pk), request, user))


@router.patch("/{pk}/")
def case_patch(pk: str, body: s.CaseDraftUpdateIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    d = body.model_dump(exclude_unset=True)
    viol = d.pop("violations", None)
    if viol is not None:
        for v in viol:
            vt = db.get(m.ViolationType, v["code"])
            if not vt or not vt.active:
                raise WorkflowError(f"Unknown violation code {v['code']}")
    for k, model in (("ward", m.Ward), ("zone", m.Zone), ("division", m.Division), ("sanctioned_plan", m.SanctionedPlan)):
        if k in d:
            d[k] = _obj(db, model, d[k], k)
    case = wf.update_draft(db, case, user, d, viol, request=request)
    return detail(db, case, request, user)


# ---------------------------------------------------------------- workflow actions
@router.post("/{pk}/submit/")
def submit(pk: str, body: s.RemarksIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    wf.submit_to_ae(db, case, user, request=request, remarks=body.remarks)
    return detail(db, case, request, user)


@router.post("/{pk}/ae_forward/")
def ae_forward(pk: str, body: s.AEForwardIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    wf.ae_forward(db, case, user, request=request, remarks=body.remarks, jc_user=_obj(db, m.User, body.jc_user, "jc_user"), recommendation=body.recommendation or "")
    return detail(db, case, request, user)


@router.post("/{pk}/ae_return/")
def ae_return(pk: str, body: s.RemarksIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    wf.ae_return(db, case, user, request=request, remarks=body.remarks)
    return detail(db, case, request, user)


@router.post("/{pk}/issue_notice/", status_code=201)
def issue_notice(pk: str, body: s.IssueNoticeIn, request: Request, user: Officer, db: DB):
    """JC issues any notice/order/memo (SCN, stop-work, sealing, demolition order, referral ...)."""
    case = get_case(db, user, pk)
    n = wf.jc_issue_notice(db, case, user, request=request, order_type_code=body.order_type, days=body.days, addressee_name=body.addressee_name,
                           addressee_address=body.addressee_address, mobiles=body.mobiles, hearing_at=body.hearing_at, hearing_venue=body.hearing_venue,
                           operative_text_en=body.operative_text_en, operative_text_hi=body.operative_text_hi, remarks=body.remarks, send_sms=body.send_sms,
                           is_final_order=body.is_final_order)
    db.flush()
    db.expire(case)
    return resp({"notice": ser.notice(n, request), "case": ser.case_detail(db, case, request, user)}, 201)


@router.post("/{pk}/record_service/")
def record_service(pk: str, body: s.RecordServiceIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    n = _obj(db, m.Notice, body.notice, "notice")
    if n.case_id != case.id:
        return resp({"detail": "Notice does not belong to this case"}, 400)
    wf.record_service(db, n, user, request=request, mode=body.mode, served_at=body.served_at, remarks=body.remarks, media_ids=body.media_ids)
    return detail(db, case, request, user)


@router.post("/{pk}/record_response/")
def record_response(pk: str, body: s.RecordResponseIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    wf.record_response(db, case, user, request=request, notice=_obj(db, m.Notice, body.notice, "notice"), received_on=body.received_on, received_via=body.received_via or "",
                       summary=body.summary, submitted_by_name=body.submitted_by_name, requests_hearing=body.requests_hearing, media_ids=body.media_ids, remarks=body.remarks)
    return detail(db, case, request, user)


@router.post("/{pk}/ae_forward_response/")
def ae_forward_response(pk: str, body: s.AECommentIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    r = _obj(db, m.CaseResponse, body.response, "response")
    if r.case_id != case.id:
        return resp({"detail": "Response does not belong to this case"}, 400)
    wf.ae_forward_response(db, r, user, request=request, comments=body.comments)
    return detail(db, case, request, user)


@router.post("/{pk}/schedule_hearing/")
def schedule_hearing(pk: str, body: s.ScheduleHearingIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    wf.schedule_hearing(db, case, user, request=request, scheduled_at=body.scheduled_at, venue=body.venue, notice=_obj(db, m.Notice, body.notice, "notice"), remarks=body.remarks)
    return detail(db, case, request, user)


@router.post("/{pk}/record_hearing/")
def record_hearing(pk: str, body: s.RecordHearingIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    h = _obj(db, m.Hearing, body.hearing, "hearing")
    if h.case_id != case.id:
        return resp({"detail": "Hearing does not belong to this case"}, 400)
    wf.record_hearing(db, h, user, request=request, proceedings=body.proceedings, attendees=body.attendees, outcome=body.outcome, next_date=body.next_date, media_ids=body.media_ids)
    return detail(db, case, request, user)


@router.post("/{pk}/drop/")
def drop(pk: str, body: s.DropIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    wf.jc_drop(db, case, user, request=request, remarks=body.remarks, regularised=body.regularised)
    return detail(db, case, request, user)


@router.post("/{pk}/record_appeal/")
def record_appeal(pk: str, body: s.RecordAppealIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    d = body.model_dump()
    remarks = d.pop("remarks")
    d["stay_order_media"] = _obj(db, m.MediaAttachment, d.get("stay_order_media"), "stay_order_media")
    d["order"] = _obj(db, m.Notice, d.get("order"), "order")
    wf.record_appeal(db, case, user, request=request, remarks=remarks, **d)
    return detail(db, case, request, user)


@router.post("/{pk}/decide_appeal/")
@router.post("/{pk}/update_appeal/")
def decide_appeal(pk: str, body: s.UpdateAppealIn, request: Request, user: Officer, db: DB):
    """Update the litigation flag: stay extended / vacated, hearing dates, later orders, final decision."""
    case = get_case(db, user, pk)
    d = body.model_dump(exclude_unset=True)
    for k in ("status", "decided_on", "decision_summary", "new_compliance_days", "stay_until", "stay_scope", "conditions", "next_hearing_on", "appeal_no", "counsel_for_mcg", "media_ids"):
        d.setdefault(k, [] if k == "media_ids" else ("" if k == "decision_summary" else None))
    appeal = _obj(db, m.Appeal, d.pop("appeal"), "appeal")
    remarks = d.pop("remarks", "")
    if appeal.case_id != case.id:
        return resp({"detail": "Appeal does not belong to this case"}, 400)
    d["stay_order_media"] = _obj(db, m.MediaAttachment, d.get("stay_order_media"), "stay_order_media")
    d["final_order_media"] = _obj(db, m.MediaAttachment, d.get("final_order_media"), "final_order_media")
    if d.get("status") == "":
        d["status"] = None
    wf.update_appeal(db, appeal, user, request=request, remarks=remarks, **d)
    return detail(db, case, request, user)


@router.post("/{pk}/record_execution/")
def record_execution(pk: str, body: s.RecordExecutionIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    d = body.model_dump()
    remarks = d.pop("remarks")
    wf.record_execution(db, case, user, request=request, remarks=remarks, **d)
    return detail(db, case, request, user)


@router.post("/{pk}/close/")
def close(pk: str, body: s.RemarksIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    wf.verify_and_close(db, case, user, request=request, remarks=body.remarks)
    return detail(db, case, request, user)


@router.post("/{pk}/reopen/")
def reopen(pk: str, body: s.RemarksIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    wf.reopen(db, case, user, request=request, remarks=body.remarks)
    return detail(db, case, request, user)


# ---------------------------------------------------------------- branch referrals & re-assignment
@router.post("/{pk}/refer_branch/")
def refer_branch(pk: str, body: s.ReferBranchIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    branch = db.get(m.Branch, body.branch)
    if not branch or not branch.active:
        raise WorkflowError(f'Invalid pk "{body.branch}" - object does not exist.')
    wf.refer_to_branch(db, case, user, request=request, branch=branch, query=body.query, due_days=body.due_days, hold_case=body.hold_case,
                       assigned_to=_obj(db, m.User, body.assigned_to, "assigned_to"), media_ids=body.media_ids, remarks=body.remarks)
    return detail(db, case, request, user)


@router.post("/{pk}/respond_branch/")
def respond_branch(pk: str, body: s.RespondReferralIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    ref = _obj(db, m.BranchReferral, body.referral, "referral")
    if ref.case_id != case.id:
        return resp({"detail": "Referral does not belong to this case"}, 400)
    wf.respond_to_referral(db, ref, user, request=request, response=body.response, recommendation=body.recommendation, media_ids=body.media_ids)
    return detail(db, case, request, user)


@router.post("/{pk}/close_referral/")
def close_referral(pk: str, body: s.CloseReferralIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    ref = _obj(db, m.BranchReferral, body.referral, "referral")
    if ref.case_id != case.id:
        return resp({"detail": "Referral does not belong to this case"}, 400)
    wf.close_referral(db, ref, user, request=request, remarks=body.remarks, withdrawn=body.withdrawn)
    return detail(db, case, request, user)


@router.post("/{pk}/reassign/")
def reassign(pk: str, body: s.ReassignIn, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    wf.reassign_case(db, case, user, request=request, assigned_ae=_obj(db, m.User, body.assigned_ae, "assigned_ae"), assigned_jc=_obj(db, m.User, body.assigned_jc, "assigned_jc"),
                     reported_by=_obj(db, m.User, body.reported_by, "reported_by"), remarks=body.remarks, order_reference=body.order_reference)
    return detail(db, case, request, user)


@router.get("/{pk}/timeline/")
def timeline(pk: str, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    events = db.query(m.CaseEvent).filter(m.CaseEvent.case_id == case.id).order_by(m.CaseEvent.at, m.CaseEvent.id).all()
    return resp({"events": [ser.case_event(e) for e in events], "chain": verify_chain(db, case)})


@router.get("/{pk}/notices/")
def case_notices(pk: str, request: Request, user: Officer, db: DB):
    case = get_case(db, user, pk)
    return resp([ser.notice(n, request) for n in case.notices])
