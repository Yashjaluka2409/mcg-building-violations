from django.http import FileResponse, Http404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Notice
from ..services.notices import dispatch_sms, render_and_sign
from .permissions import HasOfficerProfile, RoleIn
from .serializers import NoticeSerializer


class NoticeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NoticeSerializer
    queryset = Notice.objects.select_related("case", "order_type", "issued_by", "served_by").prefetch_related("dispatches", "media")
    filterset_fields = ("case", "order_type", "kind", "signature_status", "served_mode", "is_final_order")
    search_fields = ("notice_no", "case__case_no", "addressee_name", "case__pid")
    ordering_fields = ("issued_at", "served_at", "response_due_at", "compliance_due_at")
    permission_classes = [HasOfficerProfile]

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        n = self.get_object()
        f = n.signed_pdf or n.pdf
        if not f:
            raise Http404
        resp = FileResponse(f.open("rb"), content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{n.notice_no.replace("/", "-")}.pdf"'
        return resp

    @action(detail=True, methods=["post"], permission_classes=[RoleIn.of("JC", "JC_CLERK", "AE", "JE")])
    def resend_sms(self, request, pk=None):
        n = self.get_object()
        extra = request.data.get("mobiles") or []
        for mm in extra:
            if mm not in n.addressee_mobiles:
                n.addressee_mobiles.append(mm)
        n.save(update_fields=["addressee_mobiles"])
        return Response({"dispatches": [{"to": d.to, "status": d.status} for d in dispatch_sms(n)]})

    @action(detail=True, methods=["post"], permission_classes=[RoleIn.of("JC")])
    def resign(self, request, pk=None):
        """Re-run signing (e.g. after the DSC/eSign backend was configured)."""
        n = render_and_sign(self.get_object())
        return Response(NoticeSerializer(n, context={"request": request}).data)


class PublicVerifyView(APIView):
    """Public page behind the QR code: confirms that a notice number/verification code is genuine and
    shows its status. No personal data beyond what is printed on the notice."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, code):
        n = Notice.objects.select_related("case", "order_type", "issued_by").filter(verification_code=code.upper()).first()
        if not n:
            return Response({"valid": False, "detail": "No notice found for this verification code"}, status=404)
        h = request.query_params.get("h")
        hash_ok = (n.document_hash.startswith(h) if h else None)
        prof = getattr(n.issued_by, "bvms_profile", None)
        return Response({
            "valid": True, "hash_match": hash_ok, "notice_no": n.notice_no, "kind": n.kind, "order_type": n.order_type.title_en, "statute": n.order_type.statute,
            "section": n.order_type.section, "issued_at": n.issued_at, "issued_by": (prof.display_name if prof else ""), "designation": (prof.designation if prof else ""),
            "case_no": n.case.case_no, "property": {"pid": n.case.pid, "address": n.case.address_line, "ward": n.case.ward.number if n.case.ward else None},
            "addressee": n.addressee_name, "response_due_at": n.response_due_at, "compliance_due_at": n.compliance_due_at, "served_at": n.served_at,
            "signature_status": n.signature_status, "signer": n.signer_name, "document_hash": n.document_hash, "case_status": n.case.get_status_display(),
            "superseded": bool(n.superseded_by_id),
        })
