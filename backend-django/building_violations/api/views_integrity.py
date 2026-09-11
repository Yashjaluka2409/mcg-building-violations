"""Location-integrity endpoints (anti-GPS-spoofing).

POST /integrity/nonce/     -> {nonce}   single-use nonce the app binds into Play Integrity / App Attest requests
POST /integrity/precheck/  -> check     the app's home screen sends its device signals + current fix; the server
                                        answers PASS / FLAGGED / REJECTED with reasons, without recording evidence
GET  /integrity/checks/    -> list      register of checks (filter ?decision=REJECTED&officer=&context=), for admins /
                                        supervisors; the same data is exported by the "location-integrity" report
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import models as m
from ..services import location_integrity as li
from . import serializers as s
from .permissions import HasOfficerProfile, HasPerm


class IntegrityNonceView(APIView):
    permission_classes = [IsAuthenticated, HasOfficerProfile]

    def post(self, request):
        return Response({"nonce": li.issue_nonce(request.user), "ttl_s": int(li.NONCE_TTL.total_seconds())})


class IntegrityPrecheckView(APIView):
    """Body: {latitude, longitude, accuracy_m, location_integrity:{...}}. Never raises; returns the decision."""
    permission_classes = [IsAuthenticated, HasOfficerProfile]

    def post(self, request):
        d = request.data
        lat, lng = d.get("latitude"), d.get("longitude")
        chk = li.evaluate(user=request.user, request=request, context="PRECHECK", latitude=lat, longitude=lng, accuracy_m=d.get("accuracy_m"),
                          signals=d.get("location_integrity"), device_id=d.get("device_id", ""), enforce=False)
        out = li.summary(chk)
        out["advice"] = li.ADVICE if chk.decision == "REJECTED" else ""
        return Response(out)


class LocationIntegrityCheckViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = s.LocationIntegrityCheckSerializer
    permission_classes = [IsAuthenticated, HasOfficerProfile, HasPerm.of("REPORTS_EXPORT")]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ("decision", "context", "officer", "case", "task", "platform", "source")
    queryset = m.LocationIntegrityCheck.objects.select_related("officer__bvms_profile", "case").all()

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Counts by decision and the most frequent reasons (last 30 days)."""
        from collections import Counter
        from datetime import timedelta

        from django.utils import timezone
        qs = self.get_queryset().filter(at__gte=timezone.now() - timedelta(days=30))
        reasons = Counter()
        for r in qs.filter(decision__in=("REJECTED", "FLAGGED")).values_list("reasons", "flags"):
            reasons.update(list(r[0]) + list(r[1]))
        by_officer = Counter()
        for c in qs.filter(decision="REJECTED").select_related("officer__bvms_profile"):
            prof = getattr(c.officer, "bvms_profile", None)
            by_officer[prof.display_name if prof else (c.officer.get_username() if c.officer else "")] += 1
        return Response({"rejected": qs.filter(decision="REJECTED").count(), "flagged": qs.filter(decision="FLAGGED").count(),
                         "passed": qs.filter(decision="PASS").count(), "reasons": [{"code": k, "text": li.TEXT.get(k, k), "count": v} for k, v in reasons.most_common(12)],
                         "repeat_offenders": [{"officer": k, "rejections": v} for k, v in by_officer.most_common(10) if k]})
