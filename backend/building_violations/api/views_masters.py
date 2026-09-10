from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .. import models as m
from .permissions import HasOfficerProfile, IsModuleAdmin
from . import serializers as s


class _MasterViewSet(viewsets.ModelViewSet):
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [HasOfficerProfile()]
        return [IsModuleAdmin()]


class ZoneViewSet(_MasterViewSet):
    queryset = m.Zone.objects.all()
    serializer_class = s.ZoneSerializer


class DivisionViewSet(_MasterViewSet):
    queryset = m.Division.objects.select_related("zone")
    serializer_class = s.DivisionSerializer


class WardViewSet(_MasterViewSet):
    queryset = m.Ward.objects.select_related("zone", "division")
    serializer_class = s.WardSerializer
    filterset_fields = ("zone", "division")

    @action(detail=False, methods=["get"])
    def geojson(self, request):
        feats = [{"type": "Feature", "geometry": w.boundary, "properties": {"number": w.number, "name": w.name_en, "zone": w.zone.code}}
                 for w in self.get_queryset().exclude(boundary__isnull=True)]
        return Response({"type": "FeatureCollection", "features": feats})


class ViolationTypeViewSet(_MasterViewSet):
    queryset = m.ViolationType.objects.all()
    serializer_class = s.ViolationTypeSerializer
    filterset_fields = ("category", "severity", "compoundable", "active", "action_path")
    search_fields = ("code", "title_en", "title_hi", "description")


class LegalSectionViewSet(_MasterViewSet):
    queryset = m.LegalSection.objects.select_related("statute")
    serializer_class = s.LegalSectionSerializer
    filterset_fields = ("statute", "kind", "verify")
    search_fields = ("section", "heading", "text")

    @action(detail=False, methods=["get"])
    def statutes(self, request):
        return Response([{"code": x.code, "title": x.title, "citation": x.citation, "jurisdiction": x.jurisdiction, "primary": x.primary, "sections": x.sections.count()} for x in m.LegalStatute.objects.all()])


class OrderTypeViewSet(_MasterViewSet):
    queryset = m.OrderType.objects.all()
    serializer_class = s.OrderTypeSerializer
    filterset_fields = ("kind", "active")


class SLAConfigViewSet(_MasterViewSet):
    queryset = m.SLAConfig.objects.all()
    serializer_class = s.SLAConfigSerializer
