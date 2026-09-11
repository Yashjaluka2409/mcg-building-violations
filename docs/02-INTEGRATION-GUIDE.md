# 02 - Integration Guide for the MCG IT team (Austere Systems platform)

The module is built on the stack described in the IT team's *Technical Architecture & System
Clarification Report*: backend `sanitary-monitoring-system-be` (FastAPI, async SQLAlchemy 2.0, PostgreSQL /
PostGIS, JWT Bearer, S3, Pixabits, Aisensy) and frontend `web-sanitary-monitoring-system-fe` (React + Vite +
TypeScript, Tailwind, Radix, Redux Toolkit, React Query, React Hook Form + Zod, Google Maps). The folder
layout mirrors the platform's (`app/routers`, `app/services`, `app/models`, `app/repositories`,
`app/schemas`), so merging is a copy of self-contained packages plus a handful of one-line hooks.

## A. Backend (FastAPI project `sanitary-monitoring-system-be`)

1. Copy these packages into the project (they only import each other and `app.core.*`):
   `app/models/building_violations.py`, `app/schemas/building_violations/`,
   `app/repositories/building_violations.py`, `app/services/building_violations/`,
   `app/routers/building_violations/`, `app/integrations/{pid,sms,whatsapp,storage}.py`,
   `app/templates/notices/`, `app/fonts/`, plus `app/core/{templating,cache,timeutil,http,errors}.py`
   (small helpers; `http.py` is the DRF-style pagination / filtering / JSON encoder).
2. Register the models on the platform's metadata: import `app.models.building_violations` where the
   other models are imported (Alembic autogenerate then produces the `bvms_*` tables; or copy
   `alembic/versions/d133337c5b13_initial_schema_fastapi_edition.py`).
3. Include the routers in `main.py`:
   ```python
   from app.routers.building_violations import router as bv_router, public_router as bv_public
   app.include_router(bv_router)        # /building-violations/api/...
   app.include_router(bv_public)        # /building-violations/public/verify/<code>/
   ```
   Set `BVMS_USE_PLATFORM_AUTH=1` so the module's own OTP endpoints are not mounted.
4. Session: `app/routers/building_violations/deps.py` imports `get_db` from `app.db.session`. Point that
   import at the platform's `get_db` (the dependency that yields the shared `AsyncSession`). The endpoints
   run inside `AsyncSession.run_sync` (see `_router.py`), so the platform's engine, pool and transaction
   handling are used unchanged.
5. Users and tokens: the module reads the user's UUID from the JWT `sub` claim (`roles` is carried too).
   In `deps.get_current_user` replace `s.get(User, uid)` with the platform's user lookup, and make
   `OfficerProfile.user_id` a foreign key to the platform's user table (`users.id` in the standalone
   build is already a UUID). Officers (JE/AE/JC/…) are ordinary platform users with an `OfficerProfile`
   row - the same "single unified user registry" rule the report states for BWG and site operators.
6. Settings (`app/core/config.py`, pydantic-settings): the names follow the platform - `SECRET_KEY`,
   `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `DATABASE_URL`, `AWS_S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`. Merge the `PID_*`, `SMS_*`, `PIXABITS_*`, `AISENSY_*`,
   `SIGNER_*`, `PUBLIC_VERIFY_BASE`, `MCG_*` and `BVMS_*` fields into the platform's settings class.
7. `pip install -r backend/requirements.txt` adds WeasyPrint, pyHanko, qrcode, shapely, pyshp, openpyxl,
   cbor2, APScheduler (everything else the platform already has). Install Pango on the servers for Hindi PDFs.
8. `python -m app.cli migrate && python -m app.cli load-legal-catalogue` (statutes, sections, violation
   and order types, SLA defaults, workflow rules, permissions, settings, branches).
9. Periodic jobs: `app/services/building_violations/scheduler.py` registers three APScheduler jobs
   (SLA sweep 15 min, deadline sweep 60 min, SMS retry 10 min) when `BVMS_SCHEDULER=1`. On the platform
   either call `scheduler.start()` from the application lifespan (jobs are idempotent) or run
   `python -m app.cli sweep` from cron and leave the switch off.
10. Files: with `AWS_S3_BUCKET_NAME` set, evidence and notice PDFs go to S3 under `bvms/…` (keys listed in
    `integrations/storage.py`); otherwise to `UPLOADS_DIR` served at `/uploads/`. Use the platform's bucket.
11. GIS lab: create users with role `GIS_LAB`; they upload and version the government-land layers
    (GeoJSON / KML / zipped shapefile in EPSG:4326) from the portal - or run a nightly sync from the platform
    GIS into `bvms_govt_land_parcel` keyed by `layer_key`. Branch officers: role `BRANCH_OFFICER` with
    `branch` = PLANNING / REVENUE / LEGAL / ENGINEERING / FIRE.
12. Create `OfficerProfile` rows for existing users (`POST /building-violations/api/officers/`). Role and
    zones drive every permission. For the Joint Commissioner enter the Commissioner's delegation order
    number (s.401(2)) - it is printed on every notice.

### Integration points (one function each)

| Concern | File | What to do |
|---|---|---|
| PID lookup | `app/integrations/pid.py` | Either set `PID_API_USER/PASSWORD` (server-side only - see 09-SECURITY-NOTES) or set `PID_PLATFORM_PROXY_URL` to the existing backend endpoint, e.g. `https://sms-be.austere.biz/challan/property-details/{pid}`. Adjust `_normalise` if field names differ. |
| SMS (Pixabits, sender MCGGGN) | `app/integrations/sms.py` | `SMS_GATEWAY=pixabits`, `PIXABITS_API_URL`, `PIXABITS_API_KEY`, DLT template ids `SMS_DLT_TEMPLATE_SCN/ORDER`; align `PixabitsSMSGateway.build_request` with the platform's existing Pixabits helper, or call that helper from `get_gateway()`. |
| WhatsApp (Aisensy) | `app/integrations/whatsapp.py` | `AISENSY_API_KEY` + approved campaign names `AISENSY_CAMPAIGN_SCN/ORDER` (six template variables, listed in the file). Optional. |
| Digital signature | `app/services/building_violations/signing.py` | `SIGNER=local` with the MCG Document Signer certificate (.p12) for server signing; `SIGNER=pkcs11` for a USB DSC on the signing host; `SIGNER=esign` - implement `ESignSigner.sign` against the ASP (C-DAC/NSDL/eMudhra) contract. |
| Push notifications | `app/services/building_violations/notify.py` | `Notification` rows are created; wire `notify_user` to the platform's FCM sender to push to the app. |
| Building plan module | `models.SanctionedPlan` (`source=PLATFORM_SYNC`) | If the platform's *Citizen Building Plan Service* stores sanctions, write a nightly sync into `SanctionedPlan` keyed by `plan_no` (fields listed in 06-DATABASE-SCHEMA.md). |
| Government land | `/building-violations/api/gis/land-layers/` | Upload GeoJSON (WGS84) exported from the platform GIS / QGIS; or point `GovtLandParcel` at the platform's PostGIS layer table. |
| Wards / zones | `Ward.boundary`, `Zone` | Load the ward polygons the platform already has (`/geo/wards`) so the app auto-detects the ward; or map `Zone` / `Ward` onto the platform's tables in `repositories/building_violations.py` and `services/geo.py`. |
| Device attestation | `app/services/building_violations/attestation.py` | Play Integrity service account + App Attest root CA (docs/09). |

## B. Web portal (React, `web-sanitary-monitoring-system-fe`)

1. Copy `web/src/pages`, `web/src/components`, `web/src/layouts/Shell.tsx` (or reuse the platform
   shell), `web/src/api`, `web/src/i18n`, `web/src/utils`, `web/src/store` into the portal source.
2. Routes: mount under `/building-violations/*` (the platform uses per-module prefixes such as
   `/cd-waste-admin/je/...`). `web/src/App.tsx` lists the routes; the sidebar entries are in
   `Shell.tsx` and are role-filtered the same way as the platform menus.
3. Session: `web/src/store/authSlice.ts` is a Redux Toolkit slice persisted with redux-persist
   (`accessToken`, `refreshToken`, `user`). Either add it to the platform's root reducer, or drop it and
   point `bindAuthBridge()` in `web/src/api/client.ts` at the platform's auth slice - the Axios
   interceptors (Bearer injection, one-shot refresh on 401) then use the platform's tokens.
4. Data fetching is TanStack React Query (`web/src/api/endpoints.ts`); forms use React Hook Form + Zod;
   dialogs use Radix (`components/ui.tsx`); icons lucide-react; local state Zustand where needed.
5. Theme: `web/src/theme/mcg-tailwind-preset.js` replicates the platform's `primary/accent/
   secondary/danger/success/light/dark` scales. Replace it with the platform's own Tailwind preset -
   every class name used by the module exists in that preset.
6. Maps: `components/MapView.tsx` renders Google Maps (`@react-google-maps/api`) when
   `VITE_GOOGLE_MAPS_API_KEY` is set and Leaflet otherwise; both draw the same layers.
7. API base: set `VITE_API_BASE=https://sms-be.austere.biz/building-violations/api`. User ids in the
   API are UUID strings (platform user registry).
8. Public verification page `/building-violations/verify/:code` must stay reachable without login
   (it is what the QR code on every notice opens).

## C. Mobile app (MCG HARYANA - React Native / Expo)

1. Copy `mobile/app/(tabs)/*`, `mobile/app/case`, `mobile/app/inspection` as a route group (e.g.
   `app/building-violations/...`), `mobile/src/*` and the native module `mobile/modules/location-integrity`.
2. Reuse the app's existing OTP login and token storage: point `src/api/client.ts` `getToken` at the
   app's storage and set `EXPO_PUBLIC_API_BASE`.
3. Permissions already present in the app (camera, location, media) suffice; `app.json` lists the
   exact strings. `expo-sqlite` is used for the offline queue.
4. Add a "Building Violations" tile to the app home; deep-link `mcgbv://case/<id>` is registered.
5. Build with EAS (the anti-spoofing module is native code; Expo Go cannot run it) - see docs/07.

## D. Data migration / go-live checklist

- [ ] Officers and zones loaded; JC delegation order numbers entered.
- [ ] Ward boundaries and government-land layers uploaded; spot-check `gis/check-point`.
- [ ] Sanctioned-plan register imported (`sanctioned-plans/bulk_upload`, template provided).
- [ ] Paper orders imported (`legacy-orders/bulk/`, template provided) zone by zone.
- [ ] SMS DLT templates registered (two: notice, order); Pixabits credentials set; Aisensy campaigns approved (optional).
- [ ] Document Signer certificate installed; `notices/{id}/resign` re-signs earlier test notices.
- [ ] S3 bucket / prefix `bvms/` and `PUBLIC_VERIFY_BASE` set to the production portal URL (printed in every QR code).
- [ ] Location-integrity production switches turned on (docs/09) after the EAS build is distributed.
- [ ] Legal Branch has reviewed `docs/04-LEGAL-FRAMEWORK.md` items marked *verify*.
