"""Serves the built React portal (web/dist) for the standalone / sandbox deployment.
Any unknown path under /building-violations/ returns index.html so client-side routing works."""
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponseNotFound


def spa_view(request, path=""):
    dist = Path(settings.BVMS_SPA_DIST)
    candidate = (dist / path) if path else None
    if candidate and candidate.is_file() and dist in candidate.resolve().parents:
        return FileResponse(open(candidate, "rb"))
    index = dist / "index.html"
    if not index.is_file():
        return HttpResponseNotFound("Web portal not built. Run: cd web && npm run build")
    resp = FileResponse(open(index, "rb"), content_type="text/html")
    resp["Cache-Control"] = "no-store"
    return resp
