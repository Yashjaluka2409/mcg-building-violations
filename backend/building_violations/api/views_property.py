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
        for p in qs:
            b = p.bbox or []
            if bbox and len(b) == 4 and (b[2] < minx or b[0] > maxx or b[3] < miny or b[1] > maxy):
                continue
            feats.append({"type": "Feature", "id": p.id, "geometry": p.geometry,
                          "properties": {"id": p.id, "name": p.name, "agency": p.agency, "land_use": p.land_use, "village": p.village, "khasra_no": p.khasra_no, "area_sqm": p.area_sqm}})
        return Response({"type": "FeatureCollection", "features": feats})


class LandLayerUploadViewSet(viewsets.ModelViewSet):
    """Upload a GeoJSON FeatureCollection (WGS84) of government land parcels. KML/Shapefile should be
    converted to GeoJSON in QGIS (Layer > Export > Save Features As > GeoJSON, CRS EPSG:4326)."""
    serializer_class = LandLayerUploadSerializer
    queryset = LandLayerUpload.objects.all()
    permission_classes = [HasPerm.of("LAND_LAYERS_MANAGE")]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        up = serializer.save(uploaded_by=self.request.user)
        up.source_file.open("rb")
        try:
            data = json.load(up.source_file)
        finally:
            up.source_file.close()
        feats = data.get("features", []) if isinstance(data, dict) else []
        n = 0
        for f in feats:
            geom = f.get("geometry")
            if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
                continue
            props = f.get("properties") or {}
            GovtLandParcel.objects.create(
                name=str(props.get("name") or props.get("NAME") or props.get("Name") or "")[:200], agency=up.agency,
                land_use=str(props.get("land_use") or props.get("LANDUSE") or props.get("use") or "")[:120],
                village=str(props.get("village") or props.get("VILLAGE") or "")[:120], khasra_no=str(props.get("khasra") or props.get("KHASRA") or props.get("khasra_no") or "")[:120],
                area_sqm=props.get("area_sqm") or None, geometry=geom, bbox=geojson_bbox(geom), properties=props, layer_upload=up)
            n += 1
        up.feature_count = n
        up.save(update_fields=["feature_count"])
