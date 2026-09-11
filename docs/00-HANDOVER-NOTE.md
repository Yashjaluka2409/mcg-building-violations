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
