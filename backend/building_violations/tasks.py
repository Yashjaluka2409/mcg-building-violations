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
    return {"no_response": a, "execution_due": b}


@shared_task
def retry_failed_dispatches(max_attempts: int = 5):
    from .services.notices import retry_dispatch
    n = 0
    for d in NoticeDispatch.objects.filter(status="FAILED", attempts__lt=max_attempts)[:200]:
        retry_dispatch(d)
        n += 1
    return n
