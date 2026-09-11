"""
MCG Building Violation Management System - FastAPI application (standalone / sandbox entry point).

Mounted under /building-violations/ exactly like the previous edition and like the other platform modules:
    /building-violations/api/...            JSON API (Bearer JWT)
    /building-violations/public/verify/..   public QR verification (no auth)
    /api/schema/  /api/docs/                OpenAPI schema and Swagger UI
    /uploads/...                            uploaded files when S3 is off (DEBUG or DEMO_MODE; nginx in production)
    /building-violations/  /brand/...       the built React portal when SERVE_SPA=1

Inside the platform backend only the two routers are included (see app/routers/building_violations/__init__.py).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.errors import AuthError, WorkflowError
from app.core.http import BVJSONResponse, resp
from app.integrations import storage
from app.routers.building_violations import public_router, router

log = logging.getLogger("bvms")
TESTING = os.environ.get("BVMS_TESTING") == "1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.s3_enabled:
        storage.ensure_local()
    if settings.SCHEDULER and not TESTING:
        from app.services.building_violations import scheduler
        scheduler.start()
    yield
    if settings.SCHEDULER and not TESTING:
        from app.services.building_violations import scheduler
        scheduler.stop()


app = FastAPI(title="MCG Building Violation Management System API", version="2.0.0",
              description="REST API consumed by the MCG web portal module and the MCG HARYANA mobile app (building-violations module).",
              openapi_url="/api/schema/", docs_url="/api/docs/", redoc_url=None, default_response_class=BVJSONResponse, lifespan=lifespan)

origins = settings.cors_origins or ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"])


# ---------------------------------------------------------------- error envelope {"detail": ...}
@app.exception_handler(WorkflowError)
async def _workflow_error(request: Request, exc: WorkflowError):
    return resp({"detail": str(exc)}, exc.status)


@app.exception_handler(AuthError)
async def _auth_error(request: Request, exc: AuthError):
    return resp({"detail": str(exc)}, 401, headers={"WWW-Authenticate": "Bearer"})


@app.exception_handler(ValueError)
async def _value_error(request: Request, exc: ValueError):
    return resp({"detail": str(exc)}, 400)


@app.exception_handler(IntegrityError)
async def _integrity_error(request: Request, exc: IntegrityError):
    return resp({"detail": f"Database constraint violated: {str(exc.orig)[:200]}"}, 400)


@app.exception_handler(HTTPException)
async def _http_error(request: Request, exc: HTTPException):
    return resp({"detail": exc.detail} if not isinstance(exc.detail, dict) else exc.detail, exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    errors: dict = {}
    for e in exc.errors():
        loc = [str(x) for x in e.get("loc", []) if x not in ("body", "query", "path", "form")]
        errors.setdefault(".".join(loc) or "non_field_errors", []).append(e.get("msg", "Invalid value").replace("Value error, ", ""))
    detail = "; ".join(f"{k}: {', '.join(v)}" for k, v in errors.items())
    return resp({"detail": detail or "Invalid input", **errors}, 400)


# ---------------------------------------------------------------- routes
app.include_router(router)
app.include_router(public_router)
# Map library served from this server so the mobile app's map works on networks that block public CDNs.
app.mount("/building-violations/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="bvms-static")


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


if (settings.DEBUG or settings.DEMO_MODE) and not settings.s3_enabled:
    app.mount(settings.UPLOADS_URL.rstrip("/"), StaticFiles(directory=str(storage.ensure_local())), name="uploads")

if settings.SERVE_SPA:
    dist = Path(settings.SPA_DIST)

    def _spa_file(path: str):
        cand = (dist / path) if path else None
        if cand and cand.is_file() and dist.resolve() in cand.resolve().parents:
            return FileResponse(str(cand))
        index = dist / "index.html"
        if not index.is_file():
            return PlainTextResponse("Web portal not built. Run: cd web && npm run build", status_code=404)
        return FileResponse(str(index), media_type="text/html", headers={"Cache-Control": "no-store"})

    if (dist / "brand").is_dir():
        app.mount("/brand", StaticFiles(directory=str(dist / "brand")), name="brand")
    if (dist / "assets").is_dir():
        app.mount("/building-violations/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_root():
        return _spa_file("")

    @app.get("/building-violations", include_in_schema=False)
    @app.get("/building-violations/", include_in_schema=False)
    def spa_root2():
        return _spa_file("")

    @app.get("/building-violations/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(("api/", "public/")):
            raise HTTPException(404, "Not found.")
        return _spa_file(path)
