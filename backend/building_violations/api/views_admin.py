"""Administration: branches, workflow rules, settings, role permissions, officer overrides, audit log,
bulk re-assignment. Every write is recorded in AdminAuditLog with the office-order reference."""
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import models as m
from ..services import access
from ..services import workflow as wf
from .permissions import HasOfficerProfile, HasPerm
from . import serializers as s


class BranchViewSet(viewsets.ModelViewSet):
    serializer_class = s.BranchSerializer
    queryset = m.Branch.objects.prefetch_related("officers__user")
    pagination_class = None

    def get_permissions(self):
        return [HasOfficerProfile()] if self.action in ("list", "retrieve") else [HasPerm.of("BRANCH_MANAGE")()]

    def perform_create(self, serializer):
        obj = serializer.save()
        access.log_admin(self.request.user, "BRANCH_CREATE", "Branch", obj.code, after=serializer.data, order_reference=self.request.data.get("order_reference", ""), request=self.request)

    def perform_update(self, serializer):
        before = s.BranchSerializer(serializer.instance).data
        obj = serializer.save()
        access.log_admin(self.request.user, "BRANCH_UPDATE", "Branch", obj.code, before=before, after=serializer.data, order_reference=self.request.data.get("order_reference", ""), request=self.request)


class WorkflowRulesView(APIView):
    """GET -> {statuses, roles, actions, labels, matrix: {status: {role: [actions]}}}
       PUT -> {"rules": [{"status","role","action","allowed"}...], "order_reference": "..."} (partial: only listed rules change)
       POST reset -> reseed defaults"""
    permission_classes = [HasOfficerProfile]

    def get(self, request):
        access.seed_rules()
        matrix: dict = {}
        for r in m.WorkflowRule.objects.filter(allowed=True):
            matrix.setdefault(r.status, {}).setdefault(r.role, []).append(r.action)
        return Response({
            "statuses": ["*"] + [c[0] for c in m.CaseStatus.choices], "status_labels": {"*": "Any status", **dict(m.CaseStatus.choices)},
            "roles": [c[0] for c in m.Role.choices], "role_labels": dict(m.Role.choices),
            "actions": access.ALL_ACTIONS, "action_labels": access.ACTION_LABELS, "management_roles": list(access.MANAGEMENT_ROLES), "matrix": matrix,
        })

    def put(self, request):
        if not access.has_perm(request.user, "WORKFLOW_CONFIGURE"):
            return Response({"detail": "Requires permission WORKFLOW_CONFIGURE"}, status=403)
        rules = request.data.get("rules") or []
        changed = []
        for r in rules:
            if r.get("action") not in access.ALL_ACTIONS or r.get("role") not in dict(m.Role.choices) or (r.get("status") != "*" and r.get("status") not in dict(m.CaseStatus.choices)):
                return Response({"detail": f"Invalid rule {r}"}, status=400)
            obj, _ = m.WorkflowRule.objects.update_or_create(status=r["status"], role=r["role"], action=r["action"], defaults={"allowed": bool(r.get("allowed", True)), "updated_by": request.user})
            changed.append({"status": obj.status, "role": obj.role, "action": obj.action, "allowed": obj.allowed})
        access.invalidate()
        access.log_admin(request.user, "RULES_UPDATE", "WorkflowRule", "", after={"changed": changed}, order_reference=request.data.get("order_reference", ""), remarks=request.data.get("remarks", ""), request=request)
        return self.get(request)

    def post(self, request):
        if not access.has_perm(request.user, "WORKFLOW_CONFIGURE"):
            return Response({"detail": "Requires permission WORKFLOW_CONFIGURE"}, status=403)
        m.WorkflowRule.objects.all().delete()
        access.seed_rules(force=True)
        access.log_admin(request.user, "RULES_RESET", "WorkflowRule", "", order_reference=request.data.get("order_reference", ""), request=request)
        return self.get(request)


class WorkflowSettingsView(APIView):
    permission_classes = [HasOfficerProfile]

    def get(self, request):
        access.seed_settings()
        return Response(s.WorkflowSettingSerializer(m.WorkflowSetting.objects.all(), many=True).data)

    def put(self, request):
        if not access.has_perm(request.user, "WORKFLOW_CONFIGURE"):
            return Response({"detail": "Requires permission WORKFLOW_CONFIGURE"}, status=403)
        access.seed_settings()
        before, after = {}, {}
        for key, value in (request.data.get("values") or {}).items():
            row = m.WorkflowSetting.objects.filter(key=key).first()
            if not row:
                return Response({"detail": f"Unknown setting {key}"}, status=400)
            if row.value_type == "bool":
                value = bool(value)
            elif row.value_type == "int":
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    return Response({"detail": f"{key} must be an integer"}, status=400)
            before[key], after[key] = row.value, value
            row.value, row.updated_by = value, request.user
            row.save()
        access.invalidate()
        access.log_admin(request.user, "SETTING_UPDATE", "WorkflowSetting", "", before=before, after=after, order_reference=request.data.get("order_reference", ""), request=request)
        return self.get(request)


class PermissionsView(APIView):
    """GET -> catalogue + role matrix; PUT {"grants": [{"role","permission","allowed"}], "order_reference"}"""
    permission_classes = [HasOfficerProfile]

    def get(self, request):
        access.seed_permissions()
        matrix: dict = {}
        for r in m.RolePermission.objects.filter(allowed=True):
            matrix.setdefault(r.role, []).append(r.permission)
        return Response({
            "permissions": [{"code": c, "label": l, "group": g, "default_roles": roles} for c, (l, g, roles) in access.PERMISSIONS.items()],
            "roles": [c[0] for c in m.Role.choices], "role_labels": dict(m.Role.choices), "management_roles": list(access.MANAGEMENT_ROLES), "matrix": matrix,
        })

    def put(self, request):
        if not access.has_perm(request.user, "ACCESS_CONFIGURE"):
            return Response({"detail": "Requires permission ACCESS_CONFIGURE"}, status=403)
        changed = []
        for g in request.data.get("grants") or []:
            if g.get("permission") not in access.PERMISSIONS or g.get("role") not in dict(m.Role.choices):
                return Response({"detail": f"Invalid grant {g}"}, status=400)
            if g["role"] in access.MANAGEMENT_ROLES:
                continue
            obj, _ = m.RolePermission.objects.update_or_create(role=g["role"], permission=g["permission"], defaults={"allowed": bool(g.get("allowed", True)), "updated_by": request.user})
            changed.append({"role": obj.role, "permission": obj.permission, "allowed": obj.allowed})
        access.invalidate()
        access.log_admin(request.user, "PERMISSIONS_UPDATE", "RolePermission", "", after={"changed": changed}, order_reference=request.data.get("order_reference", ""), remarks=request.data.get("remarks", ""), request=request)
        return self.get(request)


class OfficerOverridesView(APIView):
    """GET/PUT per-officer permission overrides: PUT {"overrides": [{"permission","allowed","reason"}], "order_reference"}"""
    permission_classes = [HasPerm.of("ACCESS_CONFIGURE", "OFFICERS_MANAGE")]

    def get(self, request, pk):
        prof = m.OfficerProfile.objects.get(pk=pk)
        return Response({"overrides": s.OfficerPermissionOverrideSerializer(prof.permission_overrides.all(), many=True).data, "effective": sorted(access.permissions_for(prof.user)), "role_defaults": sorted(access.role_permissions().get(prof.role, set()))})

    def put(self, request, pk):
        prof = m.OfficerProfile.objects.get(pk=pk)
        before = list(prof.permission_overrides.values("permission", "allowed"))
        seen = set()
        for o in request.data.get("overrides") or []:
            if o.get("permission") not in access.PERMISSIONS:
                return Response({"detail": f"Unknown permission {o.get('permission')}"}, status=400)
            m.OfficerPermissionOverride.objects.update_or_create(profile=prof, permission=o["permission"], defaults={"allowed": bool(o.get("allowed", True)), "reason": o.get("reason", ""), "order_reference": request.data.get("order_reference", ""), "updated_by": request.user})
            seen.add(o["permission"])
        if request.data.get("replace", True):
            prof.permission_overrides.exclude(permission__in=seen).delete()
        access.invalidate()
        access.log_admin(request.user, "OFFICER_OVERRIDES_UPDATE", "OfficerProfile", prof.id, before={"overrides": before}, after={"overrides": list(prof.permission_overrides.values("permission", "allowed"))}, order_reference=request.data.get("order_reference", ""), request=request)
        return self.get(request, pk)


class AdminAuditLogView(APIView):
    permission_classes = [HasPerm.of("AUDIT_VIEW", "WORKFLOW_CONFIGURE", "ACCESS_CONFIGURE", "OFFICERS_MANAGE")]

    def get(self, request):
        qs = m.AdminAuditLog.objects.select_related("actor")
        if request.query_params.get("action"):
            qs = qs.filter(action=request.query_params["action"])
        if request.query_params.get("search"):
            q = request.query_params["search"]
            qs = qs.filter(Q(target_id__icontains=q) | Q(order_reference__icontains=q) | Q(remarks__icontains=q) | Q(actor__first_name__icontains=q))
        return Response(s.AdminAuditLogSerializer(qs[:500], many=True).data)


class BulkReassignView(APIView):
    """Re-assign many cases at once when jurisdictions change (by explicit ids, or by zone / ward / current officer)."""
    permission_classes = [HasPerm.of("CASE_REASSIGN")]

    def post(self, request):
        ser = s.BulkReassignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        qs = m.ViolationCase.objects.all()
        if d.get("case_ids"):
            qs = qs.filter(id__in=d["case_ids"])
        if d.get("zone"):
            qs = qs.filter(zone=d["zone"])
        if d.get("ward"):
            qs = qs.filter(ward=d["ward"])
        if d.get("from_user"):
            u = d["from_user"]
            qs = qs.filter(Q(assigned_ae=u) | Q(assigned_jc=u) | Q(reported_by=u))
        if d.get("only_open", True):
            qs = qs.exclude(status__in=["CLOSED", "DROPPED", "REGULARISED"])
        if not (d.get("case_ids") or d.get("zone") or d.get("ward") or d.get("from_user")):
            return Response({"detail": "Give case_ids, zone, ward or from_user"}, status=400)
        n = 0
        for case in qs[:2000]:
            wf.reassign_case(case, request.user, request=request, assigned_ae=d.get("assigned_ae"), assigned_jc=d.get("assigned_jc"), reported_by=d.get("reported_by"), remarks=d.get("remarks", ""), order_reference=d.get("order_reference", ""))
            n += 1
        access.log_admin(request.user, "CASES_REASSIGN", "ViolationCase", "", after={"count": n, "assigned_ae": getattr(d.get("assigned_ae"), "pk", None), "assigned_jc": getattr(d.get("assigned_jc"), "pk", None), "reported_by": getattr(d.get("reported_by"), "pk", None), "filters": {"zone": getattr(d.get("zone"), "pk", None), "ward": getattr(d.get("ward"), "pk", None), "from_user": getattr(d.get("from_user"), "pk", None)}}, order_reference=d.get("order_reference", ""), remarks=d.get("remarks", ""), request=request)
        return Response({"reassigned": n})
