"""Orders issued before the system (paper demolition / sealing / eviction orders) - see services/legacy.py.

POST legacy-orders/                      record one paper order (JSON, LegacyOrderSerializer) -> case detail
POST legacy-orders/bulk/                 multipart {file: CSV/XLSX with the template columns, title, order_reference} -> batch result
GET  legacy-orders/template/             CSV template with one example row
GET  legacy-orders/                      the imported orders (cases with source=LEGACY_ORDER, jurisdiction-scoped) ?status=&ward=&search=
GET  legacy-orders/summary/              counts by status
GET  legacy-orders/batches/              import batches with their row errors
POST legacy-orders/{case_id}/status/     record a historical status change from the paper file (LegacyStatusUpdateSerializer)
"""
import csv
import io

from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import models as m
from ..services import legacy
from . import serializers as s
from .permissions import HasOfficerProfile, HasPerm
from .views_cases import ViolationCaseViewSet


class LegacyOrderViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, HasOfficerProfile]
    serializer_class = s.LegacyOrderSerializer

    def _cases(self):
        # same jurisdiction scoping as the case list
        v = ViolationCaseViewSet(); v.request = self.request; v.format_kwarg = None; v.kwargs = {}
        return v.get_queryset().filter(source=legacy.LEGACY_SOURCE)

    def list(self, request):
        qs = self._cases()
        p = request.query_params
        if p.get("status"):
            qs = qs.filter(status__in=p["status"].split(","))
        if p.get("ward"):
            qs = qs.filter(ward_id=p["ward"])
        if p.get("zone"):
            qs = qs.filter(zone_id=p["zone"])
        if p.get("search"):
            from django.db.models import Q
            q = p["search"]
            qs = qs.filter(Q(case_no__icontains=q) | Q(pid__icontains=q) | Q(address_line__icontains=q) | Q(owner_name__icontains=q) | Q(final_order__notice_no__icontains=q) | Q(legacy_reference__icontains=q))
        qs = qs.order_by(p.get("ordering") or "-order_issued_at")
        page = self.paginate_queryset(qs)
        ser = s.ViolationCaseListSerializer(page if page is not None else qs, many=True, context={"request": request})
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    def create(self, request):
        ser = s.LegacyOrderSerializer(data=request.data); ser.is_valid(raise_exception=True)
        if not (request.user.bvms_profile.role in legacy.access.MANAGEMENT_ROLES or legacy.access.has_perm(request.user, "LEGACY_ORDERS_MANAGE")):
            return Response({"detail": "Requires permission: LEGACY_ORDERS_MANAGE"}, status=403)
        case = legacy.import_order(request.user, dict(ser.validated_data), request=request)
        return Response(s.ViolationCaseDetailSerializer(case, context={"request": request}).data, status=201)

    @action(detail=True, methods=["post"], url_path="status")
    def update_status(self, request, pk=None):
        case = self._cases().filter(pk=pk).first()
        if not case:
            return Response({"detail": "Not found"}, status=404)
        ser = s.LegacyStatusUpdateSerializer(data=request.data); ser.is_valid(raise_exception=True)
        legacy.update_status(case, request.user, dict(ser.validated_data), request=request)
        case.refresh_from_db()
        return Response(s.ViolationCaseDetailSerializer(case, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        return Response(legacy.summary(self._cases()))

    @action(detail=False, methods=["get"])
    def template(self, request):
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="legacy_orders_template.csv"'
        w = csv.writer(resp)
        w.writerow(legacy.TEMPLATE_COLUMNS)
        w.writerow(legacy.TEMPLATE_EXAMPLE)
        return resp

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, HasOfficerProfile, HasPerm.of("LEGACY_ORDERS_MANAGE")])
    def batches(self, request):
        return Response(s.LegacyOrderBatchSerializer(m.LegacyOrderBatch.objects.select_related("created_by")[:50], many=True).data)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, HasOfficerProfile, HasPerm.of("LEGACY_ORDERS_MANAGE")])
    def bulk(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response({"detail": "Upload a CSV or XLSX file (download the template first)"}, status=400)
        raw = f.read()
        name = (f.name or "").lower()
        if name.endswith(".xlsx"):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            ws = wb.active
            it = ws.iter_rows(values_only=True)
            header = [str(h or "").strip() for h in next(it, [])]
            rows = [dict(zip(header, [("" if v is None else (v.date().isoformat() if hasattr(v, "date") and not isinstance(v, str) else v)) for v in r])) for r in it if any(v not in (None, "") for v in r)]
        else:
            text = raw.decode("utf-8-sig", errors="replace")
            rows = [dict(r) for r in csv.DictReader(io.StringIO(text))]
        from django.core.files.base import ContentFile
        batch = legacy.import_rows(request.user, rows, title=request.data.get("title") or f.name, source_file=ContentFile(raw, name=f.name), request=request,
                                   order_reference=request.data.get("order_reference") or "")
        return Response(s.LegacyOrderBatchSerializer(batch).data, status=201)
