"""Periodic jobs (the Celery beat tasks of the Django edition), run in-process by APScheduler:

    sla_sweep               every 15 min   escalate cases past their stage SLA
    deadline_sweep          every 60 min   no-response / execution-due transitions + stay-expiry reminders
    retry_failed_dispatches every 10 min   re-send failed notice SMS

Each job opens its own session and commits. The jobs are idempotent, so several uvicorn workers running
them is harmless; for a single scheduled run set BVMS_SCHEDULER=0 and call `python -m app.cli sweep` from cron.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.timeutil import localdate, now
from app.models.building_violations import Appeal, AppealStatus, CaseStatus, Notification, NoticeDispatch, ViolationCase
from app.services.building_violations import access, sla, workflow

log = logging.getLogger(__name__)
OPEN_EXCLUDE = [CaseStatus.CLOSED, CaseStatus.DROPPED, CaseStatus.REGULARISED]


def sla_sweep(db: Session) -> int:
    n = 0
    for case in db.query(ViolationCase).filter(ViolationCase.sla_breached == False, ViolationCase.stage_due_at < now(), ViolationCase.status.notin_(OPEN_EXCLUDE)):  # noqa: E712
        sla.escalate(db, case)
        n += 1
    return n


def deadline_sweep(db: Session) -> dict:
    a = b = 0
    for case in db.query(ViolationCase).filter(ViolationCase.status == CaseStatus.SCN_SERVED, ViolationCase.response_due_at < now()).all():
        workflow.mark_no_response(db, case)
        a += 1
    for case in db.query(ViolationCase).filter(ViolationCase.status == CaseStatus.ORDER_SERVED, ViolationCase.compliance_due_at < now()).all():
        workflow.mark_execution_due(db, case)
        b += 1
    c = stay_expiry_sweep(db)
    return {"no_response": a, "execution_due": b, "stay_reminders": c}


def stay_expiry_sweep(db: Session) -> int:
    """Remind the JC / JE when a court stay is about to expire or has expired, so that either an
    extension order is uploaded or action resumes with legal backing."""
    days = int(access.get_setting(db, "stay_expiry_reminder_days", 3) or 3)
    today = localdate()
    n = 0
    day_start = now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=6)   # generous "today" window in UTC
    for ap in db.query(Appeal).filter(Appeal.status == AppealStatus.STAYED, Appeal.stay_until.isnot(None), Appeal.stay_until <= today + timedelta(days=days)).all():
        case = ap.case
        expired = ap.stay_until < today
        title = f"Stay {'EXPIRED' if expired else 'expiring'} on {case.case_no} ({ap.get_authority_display()})"
        body = f"Stay till {ap.stay_until:%d-%m-%Y}. Upload the extension order or record 'stay vacated' to resume the compliance clock."
        for u in (case.assigned_jc, case.reported_by):
            if u and not db.query(Notification.id).filter(Notification.user_id == u.id, Notification.case_id == case.id, Notification.title == title, Notification.created_at >= day_start).first():
                db.add(Notification(user_id=u.id, case_id=case.id, title=title, body=body, level="WARNING"))
                n += 1
    db.flush()
    return n


def retry_failed_dispatches(db: Session, max_attempts: int = 5) -> int:
    from app.services.building_violations.notices import retry_dispatch
    n = 0
    for d in db.query(NoticeDispatch).filter(NoticeDispatch.status == "FAILED", NoticeDispatch.attempts < max_attempts).limit(200).all():
        retry_dispatch(db, d)
        n += 1
    return n


def run_all(db: Session) -> dict:
    return {"sla": sla_sweep(db), "deadlines": deadline_sweep(db), "sms_retry": retry_failed_dispatches(db)}


# ---------------------------------------------------------------- APScheduler wiring (AsyncIOScheduler on the server's event loop)
_scheduler = None


async def _job(fn):
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            out = await db.run_sync(fn)
            await db.commit()
            log.info("%s -> %s", fn.__name__, out)
        except Exception:
            await db.rollback()
            log.exception("scheduled job %s failed", fn.__name__)


def start():
    global _scheduler
    if _scheduler:
        return _scheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(_job, "interval", minutes=15, args=[sla_sweep], id="bvms-sla-sweep", max_instances=1, coalesce=True)
    _scheduler.add_job(_job, "interval", minutes=60, args=[deadline_sweep], id="bvms-deadline-sweep", max_instances=1, coalesce=True)
    _scheduler.add_job(_job, "interval", minutes=10, args=[retry_failed_dispatches], id="bvms-sms-retry", max_instances=1, coalesce=True)
    _scheduler.start()
    return _scheduler


def stop():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
