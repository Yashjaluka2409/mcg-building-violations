"""Building Violation Management System - API routers.

Inside the MCG platform backend:
    from app.routers.building_violations import router, public_router
    app.include_router(router)          # /building-violations/api/...
    app.include_router(public_router)   # /building-violations/public/verify/<code>/
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.routers.building_violations import admin, auth, cases, dashboards, integrity, legacy, masters, media, notices, property, referrals, reports, sanctions, tasks

router = APIRouter(prefix="/building-violations/api", tags=["building-violations"])
for _r in (integrity.router, auth.router, cases.router, notices.router, media.router, property.router, sanctions.router, masters.router, dashboards.router,
           reports.router, admin.router, referrals.router, tasks.router, legacy.router):
    router.include_router(_r)
if not settings.BVMS_USE_PLATFORM_AUTH:
    router.include_router(auth.otp_router)

public_router = APIRouter(prefix="/building-violations", tags=["building-violations-public"])
public_router.include_router(notices.public)

__all__ = ["router", "public_router"]
