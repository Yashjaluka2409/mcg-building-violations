"""Planned inspections pushed by the JC / AE to the field (single, bulk CSV/XLSX, map point)."""
import csv
import io
from datetime import datetime

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .. import models as m
from ..services import access
from ..services import tasks as ts
from .permissions import HasOfficerProfile, HasPerm
from . import serializers as s

TEMPLATE_COLS = ["pid", "address", "latitude", "longitude", "ward_number", "owner_name", "owner_mobile", "category", "instructions", "priority", "assign_to_mobile"]


class InspectionTaskViewSet(viewsets.ModelViewSet):
    serializer_class = s.InspectionTaskSerializer
    permission_classes = [HasOfficerProfile]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ("status", "category", "assigned_to", "batch", "ward", "zone", "priority", "created_by")
    search_fields = ("pid", "address", "owner_name", "instructions", "batch__title")
    ordering_fields = ("created_at", "due_at", "assigned_at", "completed_at")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = m.InspectionTask.objects.select_related("ward", "zone", "created_by", "assigned_to", "batch", "related_case").prefetch_related("media", "case")
        if access.has_perm(user, "TASKS_VIEW_ALL") or user.bvms_profile.role in access.MANAGEMENT_ROLES:
            pass
        elif access.has_perm(user, "TASKS_ASSIGN"):
            qs = qs.filter(Q(created_by=user) | Q(zone__in=user.bvms_profile.zones.all()))
        else:
            qs = qs.filter(Q(assigned_to=user) | Q(assigned_to__isnull=True, zone__in=user.bvms_profile.zones.all()) | Q(assigned_to__isnull=True, ward__in=user.bvms_profile.wards.all()))
        if self.request.query_params.get("mine") == "1":
            qs = qs.filter(assigned_to=user)
        if self.request.query_params.get("open") == "1":
            qs = qs.filter(status__in=["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"])
        if self.request.query_params.get("overdue") == "1":
            qs = qs.filter(status__in=["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"], due_at__lt=timezone.now())
        return qs.distinct()

    def create(self, request, *args, **kwargs):
        ser = s.InspectionTaskCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        t = ts.create_task(request.user, **ser.validated_data)
        return Response(s.InspectionTaskSerializer(t, context={"request": request}).data, status=201)

    def _ok(self, t):
        t.refresh_from_db()
        return Response(s.InspectionTaskSerializer(t, context={"request": self.request}).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        ser = s.TaskAssignSerializer(data=request.data); ser.is_valid(raise_exception=True)
        ts.assign_task(self.get_object(), request.user, ser.validated_data["assigned_to"], ser.validated_data["remarks"])
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Field officer on site. Body: {latitude, longitude, accuracy_m}. 400 if outside the geofence."""
        ser = s.TaskStartSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        ts.start_task(self.get_object(), request.user, latitude=d["latitude"], longitude=d["longitude"], accuracy_m=d.get("accuracy_m"))
        return self._ok(self.get_object())

    @action(detail=True, methods=["get"])
    def distance(self, request, pk=None):
        """Client pre-check: ?lat&lng -> {distance_m, geofence_m, within}."""
        t = self.get_object()
        try:
            lat, lng = float(request.query_params["lat"]), float(request.query_params["lng"])
        except (KeyError, ValueError):
            return Response({"detail": "lat and lng required"}, status=400)
        dist = ts.distance_to_task(t, lat, lng)
        fence = ts.geofence_m(t)
        return Response({"distance_m": dist, "geofence_m": fence, "within": dist is None or dist <= fence})

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        ser = s.TaskCloseSerializer(data=request.data); ser.is_valid(raise_exception=True)
        d = ser.validated_data
        ts.complete_task_no_violation(self.get_object(), request.user, outcome=d["outcome"], remarks=d["remarks"], media_ids=d["media_ids"], latitude=d.get("latitude"), longitude=d.get("longitude"))
        return self._ok(self.get_object())

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        ts.cancel_task(self.get_object(), request.user, request.data.get("remarks", ""))
        return self._ok(self.get_object())

    @action(detail=False, methods=["get"])
    def counts(self, request):
        qs = self.get_queryset()
        now = timezone.now()
        return Response({"assigned_to_me": qs.filter(assigned_to=request.user, status__in=["ASSIGNED", "IN_PROGRESS"]).count(),
                         "open": qs.filter(status__in=["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"]).count(), "unassigned": qs.filter(status="UNASSIGNED").count(),
                         "overdue": qs.filter(status__in=["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"], due_at__lt=now).count(),
                         "violation_recorded": qs.filter(status="VIOLATION_RECORDED").count(), "no_violation": qs.filter(status="NO_VIOLATION").count()})

    @action(detail=False, methods=["get"])
    def geojson(self, request):
        qs = self.filter_queryset(self.get_queryset()).exclude(latitude__isnull=True)
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(t.longitude), float(t.latitude)]},
                  "properties": {"id": t.id, "kind": "task", "pid": t.pid, "address": t.address, "status": t.status, "category": t.category, "assigned_to": t.assigned_to.bvms_profile.display_name if t.assigned_to and hasattr(t.assigned_to, "bvms_profile") else None,
                                 "due_at": t.due_at, "case_id": str(t.case.id) if hasattr(t, "case") and t.case else None, "case_no": t.case.case_no if hasattr(t, "case") and t.case else None}} for t in qs[:5000]]
        return Response({"type": "FeatureCollection", "features": feats})

    @action(detail=False, methods=["get"])
    def template(self, request):
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="planned_inspections_template.csv"'
        w = csv.writer(resp)
        w.writerow(TEMPLATE_COLS)
        w.writerow(["GGN012345", "H.No. 123, Sector 14", "28.4700", "77.0450", "19", "Ramesh Kumar", "9811100001", "PG_HOSTEL", "Verify whether the building is run as a paying-guest accommodation without change of use; count rooms and occupants; check fire exits.", "NORMAL", "9000000001"])
        return resp

    @action(detail=False, methods=["post"], permission_classes=[HasPerm.of("TASKS_ASSIGN")])
    def bulk_upload(self, request):
        """multipart: file (CSV/XLSX with the template columns), title, category, instructions, due_days, assign_to (user id, optional), lookup_pid (1/0)."""
        f = request.FILES.get("file")
        if not f:
            return Response({"detail": "file is required (CSV or XLSX)"}, status=400)
        data = f.read()
        rows = []
        if (f.name or "").lower().endswith(".xlsx"):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            ws = wb.worksheets[0]
            it = ws.iter_rows(values_only=True)
            header = [str(h).strip() if h is not None else "" for h in next(it)]
            rows = [dict(zip(header, r)) for r in it if any(v not in (None, "") for v in r)]
        else:
            rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        from django.core.files.base import ContentFile
        f = ContentFile(data, name=f.name)
        assignee = None
        if request.data.get("assign_to"):
            from django.contrib.auth import get_user_model
            assignee = get_user_model().objects.filter(pk=request.data["assign_to"]).first()
        batch = ts.bulk_create_from_rows(request.user, rows, title=request.data.get("title") or f"Batch {datetime.now():%d-%m-%Y %H:%M}", category=request.data.get("category") or "VERIFICATION",
                                         instructions=request.data.get("instructions") or "", due_days=int(request.data.get("due_days") or 7), source_file=f, default_assignee=assignee,
                                         lookup_pid=str(request.data.get("lookup_pid", "1")) != "0")
        return Response(s.InspectionBatchSerializer(batch).data, status=201)


class InspectionBatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = s.InspectionBatchSerializer
    permission_classes = [HasPerm.of("TASKS_ASSIGN", "TASKS_VIEW_ALL")]
    queryset = m.InspectionBatch.objects.select_related("created_by").prefetch_related("tasks")
