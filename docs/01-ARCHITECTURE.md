# 01 - Architecture

```
 MCG HARYANA app (Expo/RN)          MCG web portal (React/Vite)            Public
 └─ building-violations module      └─ /building-violations/* routes       └─ /building-violations/verify/<code>
              │  JWT (Bearer)                    │  JWT (Bearer)                       │ no auth
              ▼                                   ▼                                    ▼
 ┌──────────────────────────────────────────────────────────────────────────────────────────────┐
 │  Django app `building_violations`  (mounted at /building-violations/ in sms-be)                │
 │  api/        REST views (DRF) - cases, notices, media, plans, gis, masters, dashboards, reports │
 │  services/   workflow (state machine), notices (render+hash+sign+SMS), pdf, signing, sla,      │
 │              audit (hash chain), geo (shapely), numbering, notify                               │
 │  integrations/ pid (DULB property API), sms (any HTTP DLT gateway)                              │
 │  tasks.py    Celery: SLA sweep, deadline sweep (no-reply / execution-due), SMS retry           │
 │  templates/notices/*.html  bilingual notice/order templates                                    │
 └──────────────────────────────────────────────────────────────────────────────────────────────┘
              │                    │                       │                     │
        PostgreSQL           /media (files)          DULB PID API          SMS gateway / DSC / eSign
```

## Design decisions

1. **Same stack as the platform.** The MCG portal is React + Vite + Tailwind with a Django-style
   REST backend (`/media/`, `access_token`/`refresh_token`, `{detail: ...}` errors, `page_size`
   pagination). The module copies these conventions so it can be mounted without adapters.
2. **No PostGIS/GDAL requirement.** Geometry is GeoJSON in JSON columns; point-in-polygon uses
   `shapely`. Swapping to PostGIS later is a model-field change only.
3. **Statute-driven configuration.** `shared/legal/*.json` is the single source of truth for
   violation types, sections, notice types and statutory minimum periods. The same JSON is bundled
   into the web/mobile clients for offline display and loaded into the DB for enforcement.
4. **Evidence integrity.** Every file is SHA-256 hashed; every workflow action is a hash-chained
   `CaseEvent`; every notice PDF is hashed and PAdES-signed; QR → public verification endpoint.
5. **Geotag enforcement.** Photos carry the GPS fix taken *at capture time* (not EXIF only). Delivery
   and execution evidence must be within `BVMS_GEOTAG_TOLERANCE_M` (default 150 m) of the case point.
6. **Two-speed timers.** SLA timers (administrative, configurable) are separate from statutory
   clocks (minimum periods enforced at issue time; deadlines computed from *service*, as s.408A
   requires "from the date of service of the notice").
7. **Roles.** JE (field), AE (review), JC (competent authority / delegated powers), JC_CLERK
   (upload replies, fix hearings only), XEN, ADDL_COMMISSIONER / COMMISSIONER / ADMIN (all + masters),
   FIELD_STAFF (service and execution evidence), VIEWER (MIS).

## Folder map

* `backend/config/` - standalone project settings (only for running the module on its own).
* `backend/building_violations/` - the pluggable app (models, api, services, integrations, templates,
  management commands `load_legal_catalogue`, `seed_demo`, tests).
* `web/src/theme/mcg-tailwind-preset.js` - the platform's colour scales; `web/src/layouts/Shell.tsx`
  - sidebar/header shell; `web/src/pages/*` - one file per screen.
* `mobile/app/*` - expo-router screens; `mobile/src/services/capture.ts` - geotagged camera capture;
  `mobile/src/services/offline.ts` - SQLite queue.
* `shared/legal/` - generator + JSON catalogue. `docs/legal-sources/` - the Acts and Code as downloaded.
