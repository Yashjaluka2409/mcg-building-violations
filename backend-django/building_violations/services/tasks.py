"""Planned inspections: the JC / AE pushes PIDs or map points to the field; the field officer can only
start the inspection within the geofence (default 100 m) of the point."""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..integrations.pid import get_pid_client
from ..models import InspectionBatch, InspectionTask, OfficerProfile, Role, Ward
from . import access
from .geo import haversine_m, ward_for_point
from .notify import notify_user
from .workflow import WorkflowError


def geofence_m(task: InspectionTask | None = None) -> int:
    return int(task.geofence_m if task and task.geofence_m else access.get_setting("inspection_geofence_m", 100))


def pick_je(ward: Ward | None, zone=None):
    if not access.get_setting("auto_assign_tasks_by_ward", True):
        return None
    if ward:
        p = OfficerProfile.objects.filter(role=Role.JE, active=True, wards=ward).first()
        if p:
            return p.user
    z = zone or (ward.zone if ward else None)
    if z:
        p = OfficerProfile.objects.filter(role=Role.JE, active=True, zones=z).first()
        if p:
            return p.user
    return None


@transaction.atomic
def create_task(user, *, pid: str = "", address: str = "", latitude=None, longitude=None, category="VERIFICATION", instructions="", priority="NORMAL",
                assigned_to=None, due_days: int | None = None, ward=None, zone=None, owner_name="", owner_mobile="", batch: InspectionBatch | None = None,
                related_case=None, lookup_pid: bool = True) -> InspectionTask:
    if not access.has_perm(user, "TASKS_ASSIGN"):
        raise WorkflowError("You do not have the TASKS_ASSIGN permission", 403)
    snap = {}
    if pid and lookup_pid and (latitude is None or not address):
        rec = get_pid_client().lookup(pid)
        if rec:
            snap = rec.as_dict()
            address = address or rec.address
            owner_name = owner_name or rec.owner_name
            owner_mobile = owner_mobile or rec.mobile
            if latitude is None and rec.latitude is not None:
                latitude, longitude = rec.latitude, rec.longitude
            if ward is None and rec.ward_no:
                ward = Ward.objects.filter(number=str(rec.ward_no).strip().lstrip("0") or "0").first() if str(rec.ward_no).strip().isdigit() else None
    if not pid and not address and latitude is None:
        raise WorkflowError("Give a PID, an address or a map point")
    if latitude is not None and longitude is not None and ward is None:
        ward = ward_for_point(latitude, longitude)
    zone = zone or (ward.zone if ward else None)
    if assigned_to is None:
        assigned_to = pick_je(ward, zone)
    days = due_days if due_days is not None else 7
    t = InspectionTask.objects.create(
        batch=batch, category=category, pid=pid or "", pid_snapshot=snap, address=address or "", owner_name=owner_name or "", owner_mobile=owner_mobile or "",
        latitude=latitude, longitude=longitude, ward=ward, zone=zone, instructions=instructions or "", priority=priority, created_by=user,
        assigned_to=assigned_to, assigned_at=timezone.now() if assigned_to else None, due_at=timezone.now() + timedelta(days=int(days)),
        status=InspectionTask.Status.ASSIGNED if assigned_to else InspectionTask.Status.UNASSIGNED, related_case=related_case, geofence_m=geofence_m())
    if assigned_to:
        notify_user(assigned_to, None, f"Inspection assigned: {t.pid or t.address[:40]}", f"{t.get_category_display()} · {t.instructions[:120]} · due {t.due_at:%d-%m-%Y}")
    return t


@transaction.atomic
def assign_task(task: InspectionTask, user, assigned_to, remarks=""):
    if not access.has_perm(user, "TASKS_ASSIGN"):
        raise WorkflowError("You do not have the TASKS_ASSIGN permission", 403)
    if task.status in (InspectionTask.Status.VIOLATION_RECORDED, InspectionTask.Status.NO_VIOLATION, InspectionTask.Status.NOT_FOUND, InspectionTask.Status.CANCELLED):
        raise WorkflowError("This inspection is already closed")
    task.assigned_to, task.assigned_at = assigned_to, timezone.now()
    task.status = InspectionTask.Status.ASSIGNED
    task.save(update_fields=["assigned_to", "assigned_at", "status", "updated_at"])
    notify_user(assigned_to, None, f"Inspection assigned: {task.pid or task.address[:40]}", remarks or task.instructions[:120])
    return task


def distance_to_task(task: InspectionTask, lat, lng) -> float | None:
    if task.latitude is None or task.longitude is None or lat is None or lng is None:
        return None
    return round(haversine_m(lat, lng, task.latitude, task.longitude), 1)


@transaction.atomic
def start_task(task: InspectionTask, user, *, latitude, longitude, accuracy_m=None):
    """The field officer presses 'Start inspection' on site. Refused outside the geofence."""
    if not access.has_perm(user, "TASKS_EXECUTE") and task.assigned_to_id != user.pk:
        raise WorkflowError("This inspection is not assigned to you", 403)
    if task.assigned_to_id and task.assigned_to_id != user.pk and not access.has_perm(user, "TASKS_ASSIGN"):
        raise WorkflowError("This inspection is assigned to another officer", 403)
    if task.status not in (InspectionTask.Status.ASSIGNED, InspectionTask.Status.UNASSIGNED, InspectionTask.Status.IN_PROGRESS):
        raise WorkflowError("This inspection is already closed")
    if latitude is None or longitude is None:
        raise WorkflowError("Device location is required to start a planned inspection")
    dist = distance_to_task(task, latitude, longitude)
    fence = geofence_m(task)
    if dist is not None and dist > fence:
        raise WorkflowError(f"You are {dist:.0f} m from the property; move within {fence} m to start the inspection", 400)
    if task.latitude is None:
        # point unknown (PID without coordinates): the officer's start location becomes the point
        task.latitude, task.longitude = latitude, longitude
        task.ward = task.ward or ward_for_point(latitude, longitude)
    task.status = InspectionTask.Status.IN_PROGRESS
    task.started_at = timezone.now()
    task.start_latitude, task.start_longitude, task.start_distance_m = latitude, longitude, dist
    if not task.assigned_to_id:
        task.assigned_to, task.assigned_at = user, timezone.now()
    task.save()
    return task


@transaction.atomic
def complete_task_no_violation(task: InspectionTask, user, *, outcome: str, remarks: str, media_ids=None, latitude=None, longitude=None):
    from ..models import MediaAttachment
    if task.assigned_to_id != user.pk and not access.has_perm(user, "TASKS_ASSIGN"):
        raise WorkflowError("This inspection is not assigned to you", 403)
    if task.status not in (InspectionTask.Status.IN_PROGRESS, InspectionTask.Status.ASSIGNED):
        raise WorkflowError("Start the inspection on site before closing it")
    if outcome not in (InspectionTask.Status.NO_VIOLATION, InspectionTask.Status.NOT_FOUND):
        raise WorkflowError("Outcome must be NO_VIOLATION or NOT_FOUND")
    if not media_ids:
        raise WorkflowError("A geotagged photograph of the property is required to close a planned inspection")
    if latitude is not None:
        dist = distance_to_task(task, latitude, longitude)
        if dist is not None and dist > geofence_m(task):
            raise WorkflowError(f"You are {dist:.0f} m from the property; the report must be filed on site")
    for m in MediaAttachment.objects.filter(id__in=media_ids):
        m.task, m.kind = task, "TASK_EVIDENCE"
        if m.latitude is not None and task.latitude is not None:
            m.distance_from_case_m = round(haversine_m(m.latitude, m.longitude, task.latitude, task.longitude), 2)
            m.geotag_verified = float(m.distance_from_case_m) <= geofence_m(task)
        m.save()
    task.status, task.completed_at, task.outcome_remarks = outcome, timezone.now(), remarks
    task.save()
    notify_user(task.created_by, None, f"Inspection closed - {task.get_status_display()}: {task.pid or task.address[:40]}", remarks[:200])
    return task


@transaction.atomic
def cancel_task(task: InspectionTask, user, remarks=""):
    if not access.has_perm(user, "TASKS_ASSIGN"):
        raise WorkflowError("You do not have the TASKS_ASSIGN permission", 403)
    task.status, task.completed_at, task.outcome_remarks = InspectionTask.Status.CANCELLED, timezone.now(), remarks
    task.save()
    return task


def link_case_to_task(task: InspectionTask, case, inspector_lat=None, inspector_lng=None):
    """Called by workflow.create_case when a case is recorded from a task. Enforces the geofence."""
    if task.status in (InspectionTask.Status.VIOLATION_RECORDED, InspectionTask.Status.CANCELLED):
        raise WorkflowError("This inspection task is already closed")
    if access.get_setting("require_geofence_for_task_inspection", True):
        if inspector_lat is None or inspector_lng is None:
            raise WorkflowError("Device location is required to record an inspection against a pushed task")
        dist = distance_to_task(task, inspector_lat, inspector_lng)
        if dist is not None and dist > geofence_m(task):
            raise WorkflowError(f"You are {dist:.0f} m from the property; the inspection must be recorded within {geofence_m(task)} m")
        case.inspector_distance_m = dist
    task.status, task.completed_at = InspectionTask.Status.VIOLATION_RECORDED, timezone.now()
    task.save(update_fields=["status", "completed_at", "updated_at"])
    case.task = task
    notify_user(task.created_by, case, f"Violation recorded on pushed inspection {task.pid or task.address[:40]}", case.case_no)


def bulk_create_from_rows(user, rows: list[dict], *, title: str, category: str, instructions: str, due_days: int, source_file=None, default_assignee=None, lookup_pid=True) -> InspectionBatch:
    batch = InspectionBatch.objects.create(title=title, category=category, created_by=user, instructions=instructions, due_at=timezone.now() + timedelta(days=due_days), source_file=source_file)
    errors = []
    n = 0
    for i, r in enumerate(rows, start=2):
        pid = str(r.get("pid") or "").strip()
        addr = str(r.get("address") or "").strip()
        lat, lng = r.get("latitude"), r.get("longitude")
        try:
            lat = float(lat) if lat not in (None, "") else None
            lng = float(lng) if lng not in (None, "") else None
        except (TypeError, ValueError):
            lat = lng = None
        if not pid and not addr and lat is None:
            errors.append({"row": i, "error": "pid, address or latitude/longitude required"})
            continue
        ward = None
        if r.get("ward_number") not in (None, ""):
            try:
                ward = Ward.objects.filter(number=int(r["ward_number"])).first()
            except (TypeError, ValueError):
                ward = None
        assignee = default_assignee
        if r.get("assign_to_mobile"):
            p = OfficerProfile.objects.filter(mobile=str(r["assign_to_mobile"]).strip()[-10:], active=True).first()
            assignee = p.user if p else assignee
        try:
            create_task(user, pid=pid, address=addr, latitude=lat, longitude=lng, category=str(r.get("category") or category), instructions=str(r.get("instructions") or instructions),
                        priority=str(r.get("priority") or "NORMAL").upper(), assigned_to=assignee, due_days=due_days, ward=ward, owner_name=str(r.get("owner_name") or ""),
                        owner_mobile=str(r.get("owner_mobile") or "")[:15], batch=batch, lookup_pid=lookup_pid)
            n += 1
        except Exception as exc:
            errors.append({"row": i, "error": str(exc)[:200]})
    batch.total, batch.errors = n, errors
    batch.save(update_fields=["total", "errors"])
    return batch
