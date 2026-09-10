"""Sanctioned building plans / licences register with bulk upload."""
import csv
import io
from datetime import datetime

from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from ..models import SanctionedPlan, Ward, Zone
from .permissions import HasOfficerProfile, RoleIn
from .serializers import SanctionedPlanSerializer

COLUMNS = ["plan_no", "pid", "address", "ward_number", "owner_name", "owner_mobile", "plot_area_sqm", "land_use", "building_type", "sanctioned_on", "valid_till",
           "sanction_mode", "permitted_floors", "permitted_ground_coverage_pct", "permitted_far", "permitted_height_m", "setback_front", "setback_rear", "setback_side",
           "licence_no", "licence_holder", "licence_date", "licence_valid_till", "licence_authority", "colony_name", "architect_name", "architect_registration_no",
           "occupation_certificate_no", "occupation_certificate_on", "latitude", "longitude", "status", "remarks"]


def _date(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


class SanctionedPlanViewSet(viewsets.ModelViewSet):
    serializer_class = SanctionedPlanSerializer
    queryset = SanctionedPlan.objects.select_related("ward", "zone").prefetch_related("documents")
    filterset_fields = ("ward", "zone", "status", "land_use", "source", "licence_authority")
    search_fields = ("plan_no", "pid", "owner_name", "address", "licence_no", "licence_holder", "colony_name")
    ordering_fields = ("sanctioned_on", "valid_till", "created_at")

    def get_permissions(self):
        if self.action in ("list", "retrieve", "by_pid", "template"):
            return [HasOfficerProfile()]
        return [RoleIn.of("JE", "AE", "JC", "XEN", "ADMIN")()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, source="MANUAL")

    @action(detail=False, methods=["get"], url_path="by-pid/(?P<pid>[^/]+)")
    def by_pid(self, request, pid=None):
        qs = self.get_queryset().filter(pid=pid)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def template(self, request):
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="sanctioned_plans_template.csv"'
        w = csv.writer(resp)
        w.writerow(COLUMNS)
        w.writerow(["MCG/BP/2026/00001", "GGN012345", "H.No. 123, Sector 14", "19", "Ramesh Kumar", "9811100001", "250.84", "Residential", "Plotted house", "2026-06-12", "2028-06-11",
                    "self-certification", "S+3", "66", "2.0", "15", "3", "3", "0", "", "", "", "", "MCG", "", "Ar. P. Mehta", "CA/2010/48211", "", "", "28.4700", "77.0450", "VALID", ""])
        return resp

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def bulk_upload(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response({"detail": "file is required (CSV or XLSX)"}, status=400)
        rows = []
        name = (f.name or "").lower()
        if name.endswith(".xlsx"):
            import openpyxl
            wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
            ws = wb.worksheets[0]
            it = ws.iter_rows(values_only=True)
            header = [str(h).strip() if h is not None else "" for h in next(it)]
            for r in it:
                rows.append(dict(zip(header, r)))
        else:
            text = io.TextIOWrapper(f.file, encoding="utf-8-sig")
            rows = list(csv.DictReader(text))
        created = updated = 0
        errors = []
        for i, r in enumerate(rows, start=2):
            plan_no = str(r.get("plan_no") or "").strip()
            if not plan_no:
                errors.append({"row": i, "error": "plan_no missing"})
                continue
            ward = Ward.objects.filter(number=int(r["ward_number"])).first() if r.get("ward_number") not in (None, "") else None
            defaults = dict(
                pid=str(r.get("pid") or "").strip(), address=str(r.get("address") or ""), ward=ward, zone=ward.zone if ward else None,
                owner_name=str(r.get("owner_name") or ""), owner_mobile=str(r.get("owner_mobile") or "")[:15], plot_area_sqm=_num(r.get("plot_area_sqm")),
                land_use=str(r.get("land_use") or ""), building_type=str(r.get("building_type") or ""), sanctioned_on=_date(r.get("sanctioned_on")) or datetime.today().date(),
                valid_till=_date(r.get("valid_till")), sanction_mode=str(r.get("sanction_mode") or ""), permitted_floors=str(r.get("permitted_floors") or ""),
                permitted_ground_coverage_pct=_num(r.get("permitted_ground_coverage_pct")), permitted_far=_num(r.get("permitted_far")), permitted_height_m=_num(r.get("permitted_height_m")),
                setbacks={k: _num(r.get(f"setback_{k}")) for k in ("front", "rear", "side") if r.get(f"setback_{k}") not in (None, "")},
                licence_no=str(r.get("licence_no") or ""), licence_holder=str(r.get("licence_holder") or ""), licence_date=_date(r.get("licence_date")),
                licence_valid_till=_date(r.get("licence_valid_till")), licence_authority=str(r.get("licence_authority") or ""), colony_name=str(r.get("colony_name") or ""),
                architect_name=str(r.get("architect_name") or ""), architect_registration_no=str(r.get("architect_registration_no") or ""),
                occupation_certificate_no=str(r.get("occupation_certificate_no") or ""), occupation_certificate_on=_date(r.get("occupation_certificate_on")),
                latitude=_num(r.get("latitude")), longitude=_num(r.get("longitude")), status=str(r.get("status") or "VALID"), remarks=str(r.get("remarks") or ""),
                source="BULK_UPLOAD", created_by=request.user)
            try:
                _, was_created = SanctionedPlan.objects.update_or_create(plan_no=plan_no, defaults=defaults)
                created += int(was_created)
                updated += int(not was_created)
            except Exception as exc:
                errors.append({"row": i, "error": str(exc)[:200]})
        return Response({"created": created, "updated": updated, "errors": errors})
