"""URL map of the module (mounted at /building-violations/ by the platform).

All JSON endpoints live under /building-violations/api/ ; the public QR verification endpoint is
/building-violations/public/verify/<code>/ (no auth).
"""
from django.conf import settings
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api import views_admin, views_auth, views_cases, views_dashboards, views_masters, views_media, views_notices, views_property, views_referrals, views_reports, views_sanctions, views_tasks, views_integrity, views_legacy

router = DefaultRouter()
router.register("cases", views_cases.ViolationCaseViewSet, basename="case")
router.register("notices", views_notices.NoticeViewSet, basename="notice")
router.register("media", views_media.MediaViewSet, basename="media")
router.register("sanctioned-plans", views_sanctions.SanctionedPlanViewSet, basename="sanctioned-plan")
router.register("gis/govt-land", views_property.GovtLandParcelViewSet, basename="govt-land")
router.register("gis/land-layers", views_property.LandLayerUploadViewSet, basename="land-layer")
router.register("masters/zones", views_masters.ZoneViewSet, basename="zone")
router.register("masters/divisions", views_masters.DivisionViewSet, basename="division")
router.register("masters/wards", views_masters.WardViewSet, basename="ward")
router.register("masters/violation-types", views_masters.ViolationTypeViewSet, basename="violation-type")
router.register("masters/legal-sections", views_masters.LegalSectionViewSet, basename="legal-section")
router.register("masters/order-types", views_masters.OrderTypeViewSet, basename="order-type")
router.register("masters/sla", views_masters.SLAConfigViewSet, basename="sla")
router.register("officers", views_auth.OfficerProfileViewSet, basename="officer")
router.register("referrals", views_referrals.BranchReferralViewSet, basename="referral")
router.register("inspections/tasks", views_tasks.InspectionTaskViewSet, basename="inspection-task")
router.register("inspections/batches", views_tasks.InspectionBatchViewSet, basename="inspection-batch")
router.register("branches", views_admin.BranchViewSet, basename="branch")
router.register("notifications", views_auth.NotificationViewSet, basename="notification")
router.register("integrity/checks", views_integrity.LocationIntegrityCheckViewSet, basename="integrity-check")
router.register("legacy-orders", views_legacy.LegacyOrderViewSet, basename="legacy-order")

api_urls = [
    path("users/me/", views_auth.MeView.as_view(), name="me"),
    path("property/pid/<str:pid>/", views_property.PIDLookupView.as_view(), name="pid-lookup"),
    path("property/nearby/", views_property.PIDNearbyView.as_view(), name="pid-nearby"),
    path("gis/check-point/", views_property.PointCheckView.as_view(), name="check-point"),
    path("dashboards/summary/", views_dashboards.SummaryView.as_view()),
    path("dashboards/funnel/", views_dashboards.StageFunnelView.as_view()),
    path("dashboards/by-area/", views_dashboards.ByZoneWardView.as_view()),
    path("dashboards/violation-mix/", views_dashboards.ViolationMixView.as_view()),
    path("dashboards/ageing/", views_dashboards.AgeingView.as_view()),
    path("dashboards/sla/", views_dashboards.SLAView.as_view()),
    path("dashboards/officers/", views_dashboards.OfficerPerformanceView.as_view()),
    path("dashboards/trends/", views_dashboards.TrendsView.as_view()),
    path("dashboards/map/", views_dashboards.MapView.as_view()),
    path("dashboards/deadlines/", views_dashboards.UpcomingDeadlinesView.as_view()),
    path("admin/workflow-rules/", views_admin.WorkflowRulesView.as_view(), name="workflow-rules"),
    path("admin/settings/", views_admin.WorkflowSettingsView.as_view(), name="workflow-settings"),
    path("admin/permissions/", views_admin.PermissionsView.as_view(), name="permissions"),
    path("admin/audit-log/", views_admin.AdminAuditLogView.as_view(), name="admin-audit-log"),
    path("admin/reassign-cases/", views_admin.BulkReassignView.as_view(), name="bulk-reassign"),
    path("officers/<int:pk>/permissions/", views_admin.OfficerOverridesView.as_view(), name="officer-overrides"),
    path("reports/", views_reports.ReportListView.as_view()),
    path("reports/<slug:name>/", views_reports.ReportView.as_view()),
]
if not getattr(settings, "BVMS_USE_PLATFORM_AUTH", False):
    api_urls += [
        path("auth/otp/request/", views_auth.OTPRequestView.as_view(), name="otp-request"),
        path("auth/otp/verify/", views_auth.OTPVerifyView.as_view(), name="otp-verify"),
    ]
    from rest_framework_simplejwt.views import TokenRefreshView
    api_urls.append(path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"))

urlpatterns = [
    path("api/integrity/nonce/", views_integrity.IntegrityNonceView.as_view()),
    path("api/integrity/precheck/", views_integrity.IntegrityPrecheckView.as_view()),
    path("api/", include(api_urls)),
    path("api/", include(router.urls)),
    path("public/verify/<str:code>/", views_notices.PublicVerifyView.as_view(), name="public-verify"),
]
