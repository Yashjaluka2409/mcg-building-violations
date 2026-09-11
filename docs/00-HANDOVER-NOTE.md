# Handover note for the MCG IT team (Austere Systems)

**Subject:** Building Violation Management System (BVMS) - code handover and sandbox deployment request

Dear team,

The Building Violation Management System has been developed as a pluggable module for the MCG platform
(the same stack and design as the Sanitary Monitoring System, per your Technical Architecture report: FastAPI +
async SQLAlchemy 2.0 + PostgreSQL backend, React + Vite + Tailwind + Redux Toolkit portal, React Native / Expo mobile app). The complete source, documentation and a one-command sandbox are in
the private repository below; you have been added as collaborators.

**Repository:** https://github.com/Yashjaluka2409/mcg-building-violations

## Requested now

1. **Deploy the sandbox** on the MCG sandbox environment (e.g. behind `sms-sandbox-fe.austere.biz`) so that
   a stable link can be shared with the Commissioner:
   ```bash
   git clone https://github.com/Yashjaluka2409/mcg-building-violations.git && cd mcg-building-violations
   docker compose -f sandbox/docker-compose.yml up -d --build
   # -> http://<server>:8000/building-violations/   (proxy this path from nginx; set PUBLIC_VERIFY_BASE to the public URL)
   ```
   `sandbox/README.md` lists the demo logins (OTP 123456 in demo mode). Demo mode must stay off in production.
2. **Review `docs/02-INTEGRATION-GUIDE.md`** and confirm the touch points with the platform: JWT/user model,
   PID API (credentials server-side), SMS gateway + DLT templates, document-signer certificate / eSign, FCM push,
   building-plan sync, ward and government-land layers.
3. **Mobile:** build the app with EAS (`mobile/eas.json`, profile `uat`) or merge the route group into the
   MCG HARYANA app as described in the guide.

## Where to look

| Need | File |
|---|---|
| Overview and quick start | `README.md` |
| Architecture | `docs/01-ARCHITECTURE.md` |
| Integration steps (backend, portal, app) | `docs/02-INTEGRATION-GUIDE.md` |
| Workflow, statutory clocks, SLA, admin configuration | `docs/03-WORKFLOW-AND-SLA.md` |
| Legal framework (36 violation types, sections, notice types) | `docs/04-LEGAL-FRAMEWORK.md`, `shared/legal/` |
| API reference / OpenAPI | `docs/05-API-REFERENCE.md`, `docs/openapi.yaml` |
| Database schema | `docs/06-DATABASE-SCHEMA.md` |
| Deployment (standalone, platform, Docker, certificates) | `docs/07-DEPLOYMENT.md`, `sandbox/` |
| Plain-language walkthrough of how it was built and how to run it | `docs/10-HOW-IT-WAS-BUILT.md` |
| UAT scenarios (45) | `docs/08-UAT-TEST-PLAN.md` |
| Security notes (incl. the PID credential exposure in the current portal bundle) | `docs/09-SECURITY-NOTES.md` |
| Sample signed notice | `docs/samples/` |

Automated tests: `cd backend && python -m pytest` (40 tests, about 20 seconds).

Please raise questions as GitHub issues on the repository so that they are tracked in one place.

Regards,
Yash Jaluka, Additional Commissioner, MCG

## Added 11 Sep 2026: location integrity (anti-GPS-spoofing)

Every geotag (evidence photo, inspector position, planned-inspection start/close) is now checked before it is
accepted: mock / fake GPS apps, software-simulated locations, rooted phones, emulators, Developer options, VPN /
proxy, stale fixes and impossible travel speeds are refused and logged; supervisors are notified; browser locations
are flagged (refused in production). Hardware attestation (Play Integrity / App Attest) and an IP-intelligence hook are
built in and switched on by configuration. **Action for the IT team:** build the app with EAS (the native module in
`mobile/modules/location-integrity` is compiled there, not in Expo Go), run UAT scenarios 37-41 on real devices, then
turn on the production switches listed in `docs/09-SECURITY-NOTES.md` → "Location integrity".

## Added 11 Sep 2026: orders issued before the system

Portal → "Orders before the system" lets the JC office record the backlog of paper demolition / sealing /
eviction orders (single entry or register upload) and keep their status current; they then flow through the same
service / stay / execution / closure machinery as new cases. See docs/03 (section "Orders issued before the
system"), docs/05 (endpoints) and UAT scenarios 42-45. Data-entry task for MCG: collect the zone-wise order
registers in the CSV template before go-live.

## Added 11 Sep 2026: server aligned with the platform stack (FastAPI edition)

Following your *Technical Architecture & System Clarification Report*, the backend was ported from Django/DRF to
the platform's own stack: **FastAPI + Pydantic v2, async SQLAlchemy 2.0 (`AsyncSession`, asyncpg), Alembic,
PostgreSQL 14+ (PostGIS-ready), JWT Bearer with the user UUID in `sub`, AWS S3 with local `/uploads` fallback,
Pixabits SMS and Aisensy WhatsApp adapters**, laid out as `app/routers`, `app/services`, `app/models`,
`app/repositories`, `app/schemas` so that it merges by copying packages (`docs/02-INTEGRATION-GUIDE.md`, section A).
The portal now uses Redux Toolkit + redux-persist for the session, Radix UI dialogs, React Query, React Hook Form +
Zod, Vite 5 and Google Maps (Leaflet fallback). Every URL, JSON shape and login the web portal and the app use is
unchanged; the 40 automated tests were ported and pass. The Django edition is kept in `backend-django/` for reference.

## Added 12 Sep 2026: configurable review hierarchy

The chain a case travels is data, not code. **Administration → Hierarchy** (permission `WORKFLOW_CONFIGURE`) shows:

* **Review chain** - ordered stages: one *reporter* stage (records the inspection), zero or more *reviewer*
  stages (review, forward or return) and one *authority* stage (issues notices and orders). Default
  Junior Engineer → Assistant Engineer → Joint Commissioner. Rename a stage ("Building Inspector",
  "Supervisor"), change the role that fills it, add a second reviewer (e.g. Executive Engineer after the AE)
  or remove the reviewer stage altogether (submissions then go straight to the authority).
* **Roles** - the role catalogue with English / Hindi names, a short label and an on/off switch; new role codes
  (e.g. `SUPERVISOR`) can be created here and then given to officers on the Officers page.

Everything downstream follows automatically: the "Submit to …" / "Forward to …" / "Return to …" buttons,
the status texts ("Pending with Supervisor"), the People card, officer pickers, dashboards and the field app
read `GET /masters/workflow-config/` (cached 5 min on the portal, cached on the phone for offline use).
A role placed in a stage inherits the workflow rules, permissions and jurisdiction scoping of that stage's
built-in role (JE / AE / JC) until the admin refines them on the other tabs. With several reviewer stages a
case visits them in order and only the stage it is at can act. Every save needs the office-order reference
and is written to the admin audit log; "Reset to default" restores the shipped chain.
Tables: `bvms_role`, `bvms_review_stage`; case column `review_stage`. Tests: `backend/tests/test_hierarchy.py`.

## Configuration the IT team enters (no code changes)

Everything below is a setting, not a change to the code. Enter the values, restart the server (and rebuild the
portal once for the map key); `backend/.env.example` lists every variable with a comment and the go-live checklist
at the end of docs/02 walks through them in order.

| Item | Where | Notes |
|---|---|---|
| Pixabits SMS (DLT, sender MCGGGN) | `backend/.env`: `SMS_GATEWAY=pixabits`, `PIXABITS_API_URL`, `PIXABITS_API_KEY`, `SMS_DLT_TEMPLATE_SCN`, `SMS_DLT_TEMPLATE_ORDER` | The adapter uses the common Pixabits request form; if your account differs, it is one method (`PixabitsSMSGateway.build_request` in `app/integrations/sms.py`). |
| Aisensy WhatsApp (optional) | `backend/.env`: `AISENSY_API_KEY`, `AISENSY_CAMPAIGN_SCN`, `AISENSY_CAMPAIGN_ORDER` | Two approved templates with the six variables listed in `app/integrations/whatsapp.py`. |
| File storage | `backend/.env`: `AWS_S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` | Files go under the `bvms/` prefix; the IAM user needs put/get/delete. Unset = local `/uploads/` folder. |
| Google Maps key | `web/.env`: `VITE_GOOGLE_MAPS_API_KEY`, then `npm run build` | Build-time setting; without it the map uses OpenStreetMap / Leaflet. |
| Database, tokens, public address | `backend/.env`: `DATABASE_URL`, `SECRET_KEY`, `PUBLIC_VERIFY_BASE` | `PUBLIC_VERIFY_BASE` is printed in every QR code; set it to the production portal URL. |
| PID API and digital signature | `backend/.env`: `PID_API_USER` / `PID_API_PASSWORD` (or `PID_PLATFORM_PROXY_URL`), `SIGNER=local` + `SIGNER_P12_PATH` / `SIGNER_P12_PASSWORD` | Credentials stay on the server only (docs/09). |
| Planned-inspection geofence | Portal → Admin → settings → "Geofence for planned inspections (metres)" | Raised to 50 000 m for the demo; set back to 100 before go-live. |
| Location-integrity production switches | Portal → Admin → settings → group "Location integrity" | Turn on "reject browser geotags", "require the native checks" and "require device attestation" once the EAS build is distributed (docs/09). |
