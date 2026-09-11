"""Branch referrals: list (scoped), and case actions refer_branch / respond_branch / close_referral."""
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .. import models as m
from ..services import access
from .permissions import HasOfficerProfile
from . import serializers as s


class BranchReferralViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = s.BranchReferralSerializer
    permission_classes = [HasOfficerProfile]
    filterset_fields = ("status", "branch", "case", "hold_case")
    search_fields = ("case__case_no", "case__address_line", "query", "response")
    ordering_fields = ("referred_at", "due_at", "responded_at")

    def get_queryset(self):
        user = self.request.user
        prof = user.bvms_profile
        qs = m.BranchReferral.objects.select_related("branch", "referred_by", "responded_by", "assigned_to", "closed_by", "case", "case__ward")
        if prof.role in access.MANAGEMENT_ROLES or access.has_perm(user, "REFERRALS_VIEW_ALL"):
            pass
        elif prof.role == m.Role.BRANCH_OFFICER:
            qs = qs.filter(Q(branch=prof.branch) | Q(assigned_to=user))
        else:
            qs = qs.filter(Q(referred_by=user) | Q(case__assigned_jc=user) | Q(case__assigned_ae=user) | Q(case__reported_by=user))
        if self.request.query_params.get("inbox") == "1":
            qs = qs.filter(status="PENDING")
        return qs

    @action(detail=False, methods=["get"])
    def counts(self, request):
        qs = self.get_queryset()
        from django.utils import timezone
        return Response({"pending": qs.filter(status="PENDING").count(), "overdue": qs.filter(status="PENDING", due_at__lt=timezone.now()).count(), "responded": qs.filter(status="RESPONDED").count()})
