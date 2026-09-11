from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from building_violations.spa import spa_view

urlpatterns = [
    path("admin/", admin.site.urls),
    # The module lives under /building-violations/ ; the platform mounts it the same way.
    path("building-violations/", include("building_violations.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
if settings.DEBUG or settings.BVMS_DEMO_MODE:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.BVMS_SERVE_SPA:
    # Single-origin sandbox: Django serves the built React portal and its brand assets.
    urlpatterns += [
        re_path(r"^brand/(?P<path>.*)$", static_serve, {"document_root": settings.BVMS_SPA_DIST / "brand"}),
        re_path(r"^building-violations/assets/(?P<path>.*)$", static_serve, {"document_root": settings.BVMS_SPA_DIST / "assets"}),
        re_path(r"^building-violations/(?!api/|public/)(?P<path>.*)$", spa_view, name="spa"),
        re_path(r"^$", spa_view, {"path": ""}, name="spa-root"),
    ]
