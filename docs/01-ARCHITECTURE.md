# 01 - Architecture

```
 MCG HARYANA app (Expo/RN)          MCG web portal (React/Vite)            Public
 └─ building-violations module      └─ /building-violations/* routes       └─ /building-violations/verify/<code>
              │  JWT (Bearer, sub = user UUID)   │  JWT (Bearer)                       │ no auth
              ▼                                   ▼                                    ▼
 ┌──────────────────────────────────────────────────────────────────────────────────────────────┐
 │  FastAPI routers `app/routers/building_violations/*`  (prefix /building-violations/api/)      │
 │    cases, notices, media, property/gis, sanctions, masters, dashboards, reports, admin,        │
 │    referrals, inspections (tasks), integrity, legacy-orders, auth (OTP only when standalone)   │
 │  app/services/building_violations/  workflow (state machine), notices (render+hash+sign+SMS), │
 │    pdf, signing, sla, audit (hash chain), geo (shapely), numbering, notify, tasks, geo_import, │
 │    location_integrity + attestation (anti-spoofing), legacy, media, scheduler (APScheduler)    │
 │  app/models/building_violations.py  SQLAlchemy 2.0 entities (bvms_* tables, users)             │
 │  app/repositories/building_violations.py  jurisdiction scoping / list queries                  │
 │  app/schemas/building_violations/  Pydantic v2 inputs, JSON output serializers                 │
 │  app/integrations/  pid (DULB property API), sms (Pixabits / HTTP DLT), whatsapp (Aisensy),    │
 │                     storage (AWS S3, local /uploads fallback)                                  │
 │  app/templates/notices/*.html  bilingual notice/order templates (Jinja2)                       │
 └──────────────────────────────────────────────────────────────────────────────────────────────┘
              │                    │                       │                     │
   PostgreSQL 14+ (asyncpg)   S3 ap-south-1 / uploads   DULB PID API      SMS / WhatsApp / DSC / eSign
```

## Design decisions

1. **Same stack as the platform** (`sanitary-monitoring-system-be` / `web-sanitary-monitoring-system-fe`,
   per the IT team's *Technical Architecture & System Clarification Report*): FastAPI + Pydantic v2,
   async SQLAlchemy 2.0 with `AsyncSession`, Alembic, PostgreSQL/PostGIS, JWT Bearer with the user's
   UUID in `sub` and the roles claim, S3 with local fallback, Pixabits SMS, Aisensy WhatsApp, a modular
   monolith laid out as `app/routers`, `app/services`, `app/models`, `app/repositories`. The portal is
   React 18 + Vite 5 + Tailwind + Radix, Redux Toolkit + redux-persist for the session, TanStack Query,
   React Hook Form + Zod, Google Maps. The API keeps the conventions the clients already use:
   `{detail}` errors, `{count,next,previous,results}` pagination, `access_token`/`refresh_token`.
2. **Async at the boundary, plain ORM code inside.** Every request gets an `AsyncSession` from the
   platform-style `get_db` dependency. The module's business logic (services, serializers) is written
   against the ordinary `Session` API and executed inside `AsyncSession.run_sync` - the pattern SQLAlchemy
   documents for ORM code that relies on lazy loading. `app/routers/building_violations/_router.py` does
   this transparently for every endpoint, so the IT team can include the routers with their own session
   factory and nothing else changes.
3. **No PostGIS/GDAL requirement.** Geometry is GeoJSON in JSON columns; point-in-polygon uses
   `shapely`. On the platform's PostGIS database a generated geometry column can be added later without
   touching the API.
4. **Statute-driven configuration.** `shared/legal/*.json` is the single source of truth for
   violation types, sections, notice types and statutory minimum periods. The same JSON is bundled
   into the web/mobile clients for offline display and loaded into the DB for enforcement.
5. **Evidence integrity.** Every file is SHA-256 hashed; every workflow action is a hash-chained
   `CaseEvent`; every notice PDF is hashed and PAdES-signed; QR → public verification endpoint; every
   geotag passes the location-integrity evaluation (anti-spoofing) before it is accepted.
6. **Geotag enforcement.** Photos carry the GPS fix taken *at capture time* (not EXIF only). Delivery
   and execution evidence must be within the admin-configured tolerance (default 150 m) of the case point.
7. **Two-speed timers.** SLA timers (administrative, configurable) are separate from statutory
   clocks (minimum periods enforced at issue time; deadlines computed from *service*, as s.408A
   requires "from the date of service of the notice"). APScheduler runs the sweeps in-process
   (or `python -m app.cli sweep` from cron).
8. **Roles.** JE (field), AE (review), JC (competent authority / delegated powers), JC_CLERK
   (upload replies, fix hearings only), XEN, ADDL_COMMISSIONER / COMMISSIONER / ADMIN (all + masters),
   FIELD_STAFF (service and execution evidence), BRANCH_OFFICER, GIS_LAB, VIEWER (MIS) - all
   admin-configurable through workflow rules, permissions and per-officer overrides.

## Folder map

* `backend/app/main.py` - standalone application (mounts the routers, `/uploads`, the built portal).
* `backend/app/routers/building_violations/` - one file per API area; `__init__.py` exposes `router`
  and `public_router` for the platform to include.
* `backend/app/services/building_violations/` - business logic; `seed.py` and `cli.py` replace the
  Django management commands (`migrate`, `load-legal-catalogue`, `seed-demo`, `sweep`, `openapi`, `serve`).
* `backend/alembic/` - migrations (`d133337c5b13` = the complete schema of this edition).
* `backend/tests/` - 40 pytest tests (httpx ASGI client + AsyncSession).
* `backend-django/` - the previous Django 5 + DRF edition, kept for reference.
* `web/src/theme/mcg-tailwind-preset.js` - the platform's colour scales; `web/src/store/` - Redux
  auth slice; `web/src/components/MapView.tsx` - Google Maps / Leaflet map; `web/src/pages/*` - one file per screen.
* `mobile/app/*` - expo-router screens; `mobile/src/services/capture.ts` + `integrity.ts` - geotagged
  capture with anti-spoofing signals; `mobile/modules/location-integrity` - native module (Kotlin / Swift).
* `shared/legal/` - generator + JSON catalogue. `docs/legal-sources/` - the Acts and Code as downloaded.
