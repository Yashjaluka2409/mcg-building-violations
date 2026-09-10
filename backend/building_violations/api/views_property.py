"""PID lookup, government-land layers and point checks."""
import json

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from ..integrations.pid import get_pid_client
from ..models import GovtLandParcel, LandLayerUpload, Ward
from ..services.geo import geojson_bbox, parcels_containing, ward_for_point
from .permissions import HasOfficerProfile, HasPerm, IsModuleAdmin
from .serializers import GovtLandParcelSerializer, LandLayerUploadSerializer, WardSerializer


class PIDLookupView(APIView):
    permission_classes = [HasOfficerProfile]

    def get(self, request, pid):
        rec = get_pid_client().lookup(pid)
        if not rec:
            return Response({"detail": "Property not found for the given PID."}, status=404)
        return Response(rec.as_dict())


class PIDNearbyView(APIView):
    permission_classes = [HasOfficerProfile]

    def get(self, request):
        try:
            lat, lng = float(request.query_params["lat"]), float(request.query_params["lng"])
        except (KeyError, ValueError):
            return Response({"detail": "lat and lng are required"}, status=400)
        return Response([r.as_dict() for r in get_pid_client().nearby(lat, lng)])


class PointCheckView(APIView):
    """Given a point: government-land parcels containing it, ward, nearby sanctioned plans."""
    permission_classes = [HasOfficerProfile]

    def get(self, request):
        try:
            lat, lng = float(request.query_params["lat"]), float(request.query_params["lng"])
        except (KeyError, ValueError):
            return Response({"detail": "lat and lng are required"}, status=400)
        buffer = float(request.query_params.get("buffer_m", 0))
        parcels = parcels_containing(lat, lng, buffer)
        ward = ward_for_point(lat, lng)
        land_type = "PRIVATE"
        if parcels:
            land_type = "GOVT_MCG" if parcels[0].agency == "MCG" else "GOVT_STATE"
        return Response({
            "land_type": land_type,
            "parcels": GovtLandParcelSerializer(parcels, many=True).data,
            "ward": WardSerializer(ward).data if ward else None,
        })


class GovtLandParcelViewSet(viewsets.ModelViewSet):
    serializer_class = GovtLandParcelSerializer
    queryset = GovtLandParcel.objects.all()
    filterset_fields = ("agency", "ward", "active", "village")
    search_fields = ("name", "khasra_no", "village", "land_use")

    def get_permissions(self):
        if self.action in ("list", "retrieve", "geojson"):
            return [HasOfficerProfile()]
        return [HasPerm.of("LAND_LAYERS_MANAGE")()]

    @action(detail=False, methods=["get"])
    def geojson(self, request):
        """GeoJSON FeatureCollection; optional ?bbox=minx,miny,maxx,maxy for map viewport loading."""
        qs = self.filter_queryset(self.get_queryset().filter(active=True))
        bbox = request.query_params.get("bbox")
        feats = []
        if bbox:
            try:
                minx, miny, maxx, maxy = [float(x) for x in bbox.split(",")]
            except ValueError:
                return Response({"detail": "bad bbox"}, status=400)
        from ..models import ViolationCase
        cases_by_parcel: dict = {}
        for c in ViolationCase.objects.filter(govt_parcel__in=qs).select_related("govt_parcel").only("id", "case_no", "status", "govt_parcel_id", "address_line", "sealed", "stop_work_issued", "litigation_status", "updated_at"):
            cases_by_parcel.setdefault(c.govt_parcel_id, []).append({"id": str(c.id), "case_no": c.case_no, "status": c.status, "address": c.address_line, "sealed": c.sealed, "stop_work": c.stop_work_issued, "litigation": c.litigation_status, "updated_at": c.updated_at})
        for p in qs:
            b = p.bbox or []
            if bbox and len(b) == 4 and (b[2] < minx or b[0] > maxx or b[3] < miny or b[1] > maxy):
                continue
            cs = cases_by_parcel.get(p.id, [])
            open_cs = [x for x in cs if x["status"] not in ("CLOSED", "DROPPED", "REGULARISED")]
            feats.append({"type": "Feature", "id": p.id, "geometry": p.geometry,
                          "properties": {"id": p.id, "name": p.name, "agency": p.agency, "land_use": p.land_use, "village": p.village, "khasra_no": p.khasra_no, "area_sqm": p.area_sqm, "layer_key": p.layer_key,
                                         "case_count": len(cs), "open_case_count": len(open_cs), "cases": cs[:20]}})
        return Response({"type": "FeatureCollection", "features": feats})


class LandLayerUploadViewSet(viewsets.ModelViewSet):
    """GIS lab: upload a government-land layer (GeoJSON / KML / KMZ / zipped shapefile, WGS84).
    Re-uploading with the same `layer_key` creates a new version and retires the old parcels."""
    serializer_class = LandLayerUploadSerializer
    queryset = LandLayerUpload.objects.select_related("uploaded_by").prefetch_related("parcels")
    permission_classes = [HasPerm.of("LAND_LAYERS_MANAGE")]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ("agency", "active", "layer_key")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [HasOfficerProfile()]
        return [HasPerm.of("LAND_LAYERS_MANAGE")()]

    def perform_create(self, serializer):
        from ..services.geo_import import import_layer
        from ..services.workflow import WorkflowError
        up = serializer.save(uploaded_by=self.request.user)
        up.source_file.open("rb")
        try:
            data = up.source_file.read()
        finally:
            up.source_file.close()
        try:
            import_layer(up, data, up.source_file.name)
        except Exception as exc:
            up.delete()
            raise WorkflowError(f"Layer could not be imported: {exc}")
        if up.feature_count == 0:
            up.delete()
            raise WorkflowError("No polygon features found in the file (check the CRS is EPSG:4326 and geometries are polygons)")
        from ..services import access
        access.log_admin(self.request.user, "LAND_LAYER_UPLOAD", "LandLayerUpload", up.id, after={"layer_key": up.layer_key, "version": up.version, "features": up.feature_count, "skipped": up.skipped_count, "format": up.file_format}, order_reference=self.request.data.get("order_reference", ""), request=self.request)

    def perform_destroy(self, instance):
        """Retire a layer version (parcels become inactive); nothing is physically deleted."""
        instance.active = False
        instance.save(update_fields=["active"])
        GovtLandParcel.objects.filter(layer_upload=instance).update(active=False)
        from ..services import access
        access.log_admin(self.request.user, "LAND_LAYER_RETIRE", "LandLayerUpload", instance.id, order_reference=self.request.data.get("order_reference", "") if hasattr(self.request, "data") else "", request=self.request)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        up = self.get_object()
        LandLayerUpload.objects.filter(layer_key=up.layer_key, active=True).exclude(pk=up.pk).update(active=False)
        GovtLandParcel.objects.filter(layer_key=up.layer_key).update(active=False)
        up.active = True
        up.save(update_fields=["active"])
        GovtLandParcel.objects.filter(layer_upload=up).update(active=True)
        return Response(LandLayerUploadSerializer(up).data)
