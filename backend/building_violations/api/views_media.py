from django.utils import timezone
from rest_framework import viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from ..models import MediaAttachment
from ..services.geo import haversine_m
from .permissions import HasOfficerProfile
from .serializers import MediaAttachmentSerializer, MediaUploadSerializer

IMAGE_EXT = {"jpg", "jpeg", "png", "heic", "webp"}
VIDEO_EXT = {"mp4", "mov", "m4v", "3gp", "webm"}
DOC_EXT = {"pdf", "doc", "docx", "xls", "xlsx"}


class MediaViewSet(viewsets.ModelViewSet):
    """POST multipart {file, kind, case?, latitude, longitude, accuracy_m, captured_at, device_id, caption}.
    The mobile app captures photos/videos in-app and posts the GPS fix read at capture time; the server
    stores the fix, hashes the file and (when a case is given) computes the distance to the case point."""
    serializer_class = MediaAttachmentSerializer
    permission_classes = [HasOfficerProfile]
    parser_classes = [MultiPartParser, FormParser]
    queryset = MediaAttachment.objects.select_related("uploaded_by")
    filterset_fields = ("case", "kind", "notice", "sanctioned_plan")
    http_method_names = ["get", "post", "delete", "head", "options"]

    def create(self, request, *args, **kwargs):
        s = MediaUploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        f = d["file"]
        ext = (f.name.rsplit(".", 1)[-1] if "." in f.name else "").lower()
        media_type = "IMAGE" if ext in IMAGE_EXT else "VIDEO" if ext in VIDEO_EXT else "PDF" if ext == "pdf" else "DOC" if ext in DOC_EXT else "OTHER"
        if media_type == "OTHER":
            return Response({"detail": f"Unsupported file type .{ext}"}, status=400)
        att = MediaAttachment(
            case=d.get("case"), notice=d.get("notice"), sanctioned_plan=d.get("sanctioned_plan"), kind=d["kind"], media_type=media_type, file=f,
            original_name=f.name[:255], latitude=d.get("latitude"), longitude=d.get("longitude"), accuracy_m=d.get("accuracy_m"), altitude_m=d.get("altitude_m"),
            captured_at=d.get("captured_at") or timezone.now(), device_id=d.get("device_id") or request.headers.get("X-Device-Id", ""), caption=d.get("caption", ""),
            uploaded_by=request.user)
        case = d.get("case")
        if case and case.latitude is not None and att.latitude is not None:
            from ..services import access
            att.distance_from_case_m = round(haversine_m(att.latitude, att.longitude, case.latitude, case.longitude), 2)
            att.geotag_verified = float(att.distance_from_case_m) <= access.geotag_tolerance_m()
        att.save()
        if case:
            from ..services.audit import record_event
            record_event(case, "MEDIA_ADDED", actor=request.user, from_status=case.status, to_status=case.status, request=request,
                         payload={"media_id": str(att.id), "kind": att.kind, "type": media_type, "geotag_verified": att.geotag_verified}, lat=att.latitude, lng=att.longitude)
        return Response(MediaAttachmentSerializer(att, context={"request": request}).data, status=201)

    def perform_destroy(self, instance):
        # evidence is never hard-deleted once the case has left DRAFT
        if instance.case and instance.case.status != "DRAFT":
            from ..services.workflow import WorkflowError
            raise WorkflowError("Evidence cannot be deleted after the case is submitted", 403)
        instance.delete()
