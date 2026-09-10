"""OTP login (standalone mode), current user, notifications, officer administration.

When BVMS_USE_PLATFORM_AUTH=1 the platform's /auth/otp/* endpoints are used instead and these two
OTP views are simply not routed (see urls.py)."""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from ..integrations.sms import get_gateway, normalise_mobile
from ..models import Notification, OfficerProfile, OTPRequest
from .permissions import HasOfficerProfile, IsModuleAdmin
from .serializers import MeSerializer, NotificationSerializer, OfficerProfileSerializer, OTPRequestSerializer, OTPVerifySerializer

User = get_user_model()


def _hash(code):
    return hashlib.sha256(code.encode()).hexdigest()


class OTPRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = OTPRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        mobile = normalise_mobile(s.validated_data["mobile"])
        if not mobile:
            return Response({"detail": "Enter a valid 10-digit mobile number"}, status=400)
        prof = OfficerProfile.objects.filter(mobile=mobile, active=True).first()
        if not prof:
            return Response({"detail": "This mobile number is not registered as an officer of the Building Violation module"}, status=404)
        code = settings.BVMS_OTP_DEMO_CODE if settings.DEBUG else f"{secrets.randbelow(10**6):06d}"
        OTPRequest.objects.create(mobile=mobile, code_hash=_hash(code), expires_at=timezone.now() + timedelta(minutes=10))
        get_gateway().send(mobile, f"{code} is your OTP for MCG Building Violation System. Valid 10 minutes. - MCGGGN", "")
        return Response({"detail": "OTP sent", "expires_in": 600})


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = OTPVerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        mobile = normalise_mobile(s.validated_data["mobile"])
        otp = OTPRequest.objects.filter(mobile=mobile, consumed=False, expires_at__gt=timezone.now()).order_by("-created_at").first()
        if not otp or otp.attempts >= 5:
            return Response({"detail": "OTP expired or too many attempts; request a new OTP"}, status=400)
        if otp.code_hash != _hash(s.validated_data["otp"].strip()):
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            return Response({"detail": "Incorrect OTP"}, status=400)
        otp.consumed = True
        otp.save(update_fields=["consumed"])
        prof = OfficerProfile.objects.select_related("user").get(mobile=mobile, active=True)
        refresh = RefreshToken.for_user(prof.user)
        return Response({"access_token": str(refresh.access_token), "refresh_token": str(refresh), "user": _me_payload(prof.user)})


def _me_payload(user):
    prof = getattr(user, "bvms_profile", None)
    return MeSerializer({
        "id": user.pk, "username": user.get_username(), "name": prof.display_name if prof else user.get_username(),
        "role": prof.role if prof else None, "designation": prof.designation if prof else "", "mobile": prof.mobile if prof else "",
        "zones": prof.zones.all() if prof else [], "wards": prof.wards.all() if prof else [],
        "delegation_order_no": prof.delegation_order_no if prof else "",
        "unread_notifications": Notification.objects.filter(user=user, read_at__isnull=True).count(),
    }).data


class MeView(APIView):
    permission_classes = [HasOfficerProfile]

    def get(self, request):
        return Response(_me_payload(request.user))


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [HasOfficerProfile]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"])
    def mark_read(self, request):
        ids = request.data.get("ids")
        qs = self.get_queryset().filter(read_at__isnull=True)
        if ids:
            qs = qs.filter(id__in=ids)
        n = qs.update(read_at=timezone.now())
        return Response({"updated": n})


class OfficerProfileViewSet(viewsets.ModelViewSet):
    """Officer directory. Admin creates JE/AE/JC/clerk logins; JC can create its own clerk sub-login."""
    serializer_class = OfficerProfileSerializer
    queryset = OfficerProfile.objects.select_related("user").prefetch_related("zones", "wards", "divisions")
    filterset_fields = ("role", "active", "zones")
    search_fields = ("user__first_name", "user__last_name", "mobile", "designation", "employee_code")

    def get_permissions(self):
        if self.action in ("list", "retrieve", "dropdown"):
            return [HasOfficerProfile()]
        return [HasOfficerProfile()]

    def perform_create(self, serializer):
        me = self.request.user.bvms_profile
        role = serializer.validated_data.get("role")
        if me.role == "JC":
            if role != "JC_CLERK":
                from ..services.workflow import WorkflowError
                raise WorkflowError("A Joint Commissioner may only create clerk sub-logins", 403)
            serializer.save(parent_profile=me)
            return
        if me.role not in ("ADMIN", "COMMISSIONER", "ADDL_COMMISSIONER"):
            from ..services.workflow import WorkflowError
            raise WorkflowError("Only the module administrator can create officer logins", 403)
        serializer.save()

    def perform_update(self, serializer):
        me = self.request.user.bvms_profile
        if me.role not in ("ADMIN", "COMMISSIONER", "ADDL_COMMISSIONER") and serializer.instance.parent_profile_id != me.id and serializer.instance.id != me.id:
            from ..services.workflow import WorkflowError
            raise WorkflowError("Not allowed to edit this officer", 403)
        serializer.save()

    @action(detail=False, methods=["get"])
    def dropdown(self, request):
        role = request.query_params.get("role")
        qs = self.get_queryset().filter(active=True)
        if role:
            qs = qs.filter(role=role)
        zone = request.query_params.get("zone")
        if zone:
            qs = qs.filter(zones__id=zone) | qs.filter(zones__isnull=True)
        return Response([{"user_id": p.user_id, "name": p.display_name, "role": p.role, "designation": p.designation} for p in qs.distinct()])
