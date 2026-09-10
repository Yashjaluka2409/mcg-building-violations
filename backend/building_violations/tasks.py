"""Celery tasks: SLA sweep, statutory deadline sweep, SMS retries."""
from celery import shared_task
from django.utils import timezone

from .models import CaseStatus, NoticeDispatch, ViolationCase
from .services import sla, workflow


@shared_task
def sla_sweep():
    now = timezone.now()
    n = 0
    for case in ViolationCase.objects.filter(sla_breached=False, stage_due_at__lt=now).exclude(status__in=[CaseStatus.CLOSED, CaseStatus.DROPPED, CaseStatus.REGULARISED]):
        sla.escalate(case)
        n += 1
    return n


@shared_task
def deadline_sweep():
    now = timezone.now()
    a = b = 0
    for case in ViolationCase.objects.filter(status=CaseStatus.SCN_SERVED, response_due_at__lt=now):
        workflow.mark_no_response(case)
        a += 1
    for case in ViolationCase.objects.filter(status=CaseStatus.ORDER_SERVED, compliance_due_at__lt=now):
        workflow.mark_execution_due(case)
        b += 1
    c = stay_expiry_sweep()
    return {"no_response": a, "execution_due": b, "stay_reminders": c}


@shared_task
def stay_expiry_sweep():
    """Remind the JC / JE when a court stay is about to expire or has expired, so that either an
    extension order is uploaded or action resumes with legal backing."""
    from datetime import timedelta
    from .models import Appeal, Notification
    from .services import access
    days = int(access.get_setting("stay_expiry_reminder_days", 3) or 3)
    today = timezone.localdate()
    n = 0
    for ap in Appeal.objects.filter(status=Appeal.Status.STAYED, stay_until__isnull=False, stay_until__lte=today + timedelta(days=days)).select_related("case"):
        case = ap.case
        expired = ap.stay_until < today
        title = f"Stay {'EXPIRED' if expired else 'expiring'} on {case.case_no} ({ap.get_authority_display()})"
        body = f"Stay till {ap.stay_until:%d-%m-%Y}. Upload the extension order or record 'stay vacated' to resume the compliance clock."
        for u in (case.assigned_jc, case.reported_by):
            if u and not Notification.objects.filter(user=u, case=case, title=title, created_at__date=today).exists():
                Notification.objects.create(user=u, case=case, title=title, body=body, level="WARNING")
                n += 1
    return n


@shared_task
def retry_failed_dispatches(max_attempts: int = 5):
    from .services.notices import retry_dispatch
    n = 0
    for d in NoticeDispatch.objects.filter(status="FAILED", attempts__lt=max_attempts)[:200]:
        retry_dispatch(d)
        n += 1
    return n
