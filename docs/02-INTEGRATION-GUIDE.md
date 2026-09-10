# 02 - Integration Guide for the MCG IT team (Austere Systems platform)

The module was written against the conventions visible in the production bundle of
`https://mcg-sms.austere.biz` (React + Vite + Tailwind, Django-style REST at `sms-be.austere.biz`,
JWT `access_token`/`refresh_token`, OTP login, roles JE/AE/XEN/JC/ADMIN, PID lookups on
`property.ulbharyana.gov.in`). We did **not** have access to the GitLab source
(`git.austeresystems.com/mcg-sanitary-monitoring-system/*`), so the steps below describe the
touch points; each is a small, well-marked change.

## A. Backend (Django project `sms-be`)

1. Copy `backend/building_violations/` into the project (next to the other apps).
2. `INSTALLED_APPS += ["building_violations"]` (needs `rest_framework`, `django_filters`,
   `corsheaders`, `drf_spectacular` which the platform already uses).
3. Root `urls.py`: `path("building-violations/", include("building_violations.urls"))`.
4. Copy the `BVMS_*` block from `backend/config/settings.py` and set `BVMS_USE_PLATFORM_AUTH = True`
   → the module's own OTP endpoints are not routed and the platform's JWT is used as-is
   (`rest_framework_simplejwt.authentication.JWTAuthentication`). If the platform uses a different
   user model, nothing changes: the module only references `settings.AUTH_USER_MODEL`.
5. `pip install -r backend/requirements.txt` (adds WeasyPrint, pyHanko, qrcode, shapely, openpyxl).
   Install Pango on the servers for Hindi PDFs.
6. `python manage.py migrate building_violations && python manage.py load_legal_catalogue`.
7. Create `OfficerProfile` rows for existing users (Django admin → *Officer profiles*, or the
   `/building-violations/api/officers/` endpoint). Role and zones drive every permission.
   For the Joint Commissioner enter the Commissioner's delegation order number (s.401(2)) - it is
   printed on every notice.
8. Celery: the module registers three periodic tasks (`bvms-sla-sweep` 15 min, `bvms-deadline-sweep`
   hourly, `bvms-sms-retry` 10 min). Add them to the platform's beat schedule (see `CELERY_BEAT_SCHEDULE`
   in `config/settings.py`). Without Celery the sweeps can be run from cron:
   `python manage.py shell -c "from building_violations import tasks; tasks.deadline_sweep(); tasks.sla_sweep()"`.
9. Media: the module writes under `MEDIA_ROOT/bvms/...` - the same volume served at `/media/`.

### Integration points (one function each)

| Concern | File | What to do |
|---|---|---|
| PID lookup | `integrations/pid.py` | Either set `PID_API_USER/PASSWORD` (server-side; the credentials are currently embedded in the portal's JavaScript bundle - see 09-SECURITY-NOTES) or set `PID_PLATFORM_PROXY_URL` to the existing backend endpoint, e.g. `https://sms-be.austere.biz/challan/property-details/{pid}`. Adjust `_normalise` if field names differ. |
| SMS | `integrations/sms.py` | `SMS_GATEWAY=http`, `SMS_HTTP_URL`, auth header, DLT template ids; adapt `HttpSMSGateway.build_request` to the provider's JSON. |
| Digital signature | `services/signing.py` | `SIGNER=local` with the MCG Document Signer certificate (.p12) for server signing; `SIGNER=pkcs11` for a USB DSC on the signing host; `SIGNER=esign` - implement `ESignSigner.sign` against the ASP (C-DAC/NSDL/eMudhra) contract. |
| Push notifications | `services/notify.py` | `Notification` rows are created; wire `notify_user` to the platform's FCM sender to push to the app. |
| Building plan module | `models.SanctionedPlan` (`source=PLATFORM_SYNC`) | If the platform's *Citizen Building Plan Service* stores sanctions, write a nightly sync into `SanctionedPlan` keyed by `plan_no` (fields listed in 06-DATABASE-SCHEMA.md). |
| Government land | `/building-violations/api/gis/land-layers/` | Upload GeoJSON (WGS84) exported from the platform GIS / QGIS; or point `GovtLandParcel` at the platform's layer table. |
| Wards | `Ward.boundary` | Load the ward polygons the platform already has (`/geo/wards`) so the app auto-detects the ward. |

## B. Web portal (React)

1. Copy `web/src/pages`, `web/src/components`, `web/src/layouts/Shell.tsx` (or reuse the platform
   shell), `web/src/api`, `web/src/i18n`, `web/src/utils`, `web/src/store` into the portal source.
2. Routes: mount under `/building-violations/*` (the platform uses per-module prefixes such as
   `/cd-waste-admin/je/...`). `web/src/App.tsx` lists the routes; the sidebar entries are in
   `Shell.tsx` and are role-filtered the same way as the platform menus.
3. Theme: `web/src/theme/mcg-tailwind-preset.js` replicates the platform's `primary/accent/
   secondary/danger/success/light/dark` scales. Replace it with the platform's own Tailwind preset -
   every class name used by the module exists in that preset.
4. API base: set `VITE_API_BASE=https://sms-be.austere.biz/building-violations/api`; tokens are read
   from `localStorage.accessToken/refreshToken` (same keys as the platform).
5. Public verification page `/building-violations/verify/:code` must stay reachable without login
   (it is what the QR code on every notice opens).

## C. Mobile app (MCG HARYANA - React Native / Expo)

1. Copy `mobile/app/(tabs)/*`, `mobile/app/case`, `mobile/app/inspection` as a route group (e.g.
   `app/building-violations/...`) and `mobile/src/*` into the app.
2. Reuse the app's existing OTP login and token storage: point `src/api/client.ts` `getToken` at the
   app's storage and set `EXPO_PUBLIC_API_BASE`.
3. Permissions already present in the app (camera, location, media) suffice; `app.json` lists the
   exact strings. `expo-sqlite` is used for the offline queue.
4. Add a "Building Violations" tile to the app home; deep-link `mcgbv://case/<id>` is registered.
5. If the app is not Expo-based, the screens are plain React Native and only `expo-camera`,
   `expo-location`, `expo-image-picker`, `expo-sqlite`, `expo-secure-store` need replacing by the
   app's equivalents (`react-native-vision-camera`, `react-native-geolocation-service`, etc.).

## D. Data migration / go-live checklist

- [ ] Officers and zones loaded; JC delegation order numbers entered.
- [ ] Ward boundaries and government-land layers uploaded; spot-check `gis/check-point`.
- [ ] Sanctioned-plan register imported (`sanctioned-plans/bulk_upload`, template provided).
- [ ] SMS DLT templates registered (two: notice, order) and gateway credentials set.
- [ ] Document Signer certificate installed; `notices/{id}/resign` re-signs earlier test notices.
- [ ] `PUBLIC_VERIFY_BASE` set to the production portal URL (printed in every QR code).
- [ ] Legal Branch has reviewed `docs/04-LEGAL-FRAMEWORK.md` items marked *verify*.
