# MCG Building Violation Management System (BVMS)

A complete, integration-ready module for the Municipal Corporation Gurugram IT platform that takes a
building violation from **field inspection → AE review → Joint Commissioner → show-cause notice
(digitally signed, QR-verified, SMS-delivered) → reply / hearing → demolition or sealing order → 15-day
compliance clock → geotagged proof of execution**, under the Haryana Municipal Corporation Act, 1994,
the Haryana Building Code, 2017 and the Haryana Public Premises Act, 1972.

The code follows the MCG platform's own stack (see `docs/01-ARCHITECTURE.md`) so that it merges into
`sanitary-monitoring-system-be` / `web-sanitary-monitoring-system-fe` by copying packages, not by rewriting.

| Part | Folder | Stack | Status |
|---|---|---|---|
| Backend / API | `backend/` | FastAPI + Pydantic v2, async SQLAlchemy 2.0 (asyncpg / aiosqlite), Alembic, PostgreSQL 14+ (PostGIS-ready; SQLite for the demo), JWT (PyJWT), APScheduler, WeasyPrint, pyHanko (PAdES), S3 or local uploads | Runs; **40 end-to-end tests pass** (`pytest`) |
| Web portal module | `web/` | React 18 + Vite 5 + TypeScript, Tailwind 3.4 (MCG theme tokens), Radix UI, lucide-react, Redux Toolkit + redux-persist (session), Zustand, Axios, TanStack Query v5, React Hook Form + Zod, Google Maps JS API (Leaflet fallback), Recharts, i18next (EN/HI) | Type-checks and builds; served by the backend in the sandbox |
| Mobile app module (iOS + Android) | `mobile/` | React Native / Expo SDK 57, expo-router, expo-camera/location, SQLite offline queue, native anti-spoofing module (Kotlin / Swift) | Runs in Expo Go, iOS simulator and Android emulator; build with EAS |
| Legal catalogue | `shared/legal/` | 5 statutes, 125 sections, 36 violation types, 28 notice/order types (JSON, single source of truth) | Complete; "verify" flags for Legal Branch |
| Documentation | `docs/` | Architecture, integration guide, workflow/SLA, legal framework, API (OpenAPI), DB schema, deployment, UAT plan, security notes, plain-language walkthrough | Complete |
| Previous edition | `backend-django/` | The Django 5 + DRF implementation the FastAPI backend was ported from (kept for reference; same endpoints and JSON) | Archived |

## Sandbox / demo

`./sandbox/run_sandbox.sh --tunnel` serves the portal + API from one origin and prints a public
`https://<random>.trycloudflare.com/building-violations/` link (see `sandbox/README.md`; Docker files for
the IT team's sandbox are there too; `sandbox/funnel.sh` / `sandbox/ngrok_tunnel.sh` give a stable address).
Source: https://github.com/Yashjaluka2409/mcg-building-violations.

## Quick start (demo on one machine)

```bash
# 1. Backend (Python 3.11+; Pango for Hindi PDFs: `brew install pango` / `apt install libpango-1.0-0 libpangoft2-1.0-0`)
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                     # DEMO_MODE=1 for the fixed OTP and demo PID records
python -m app.cli migrate && python -m app.cli seed-demo --with-cases
python -m app.cli serve                  # http://127.0.0.1:8000/api/docs/  (uvicorn with reload)
python -m pytest                         # 40 tests, about 20 seconds
# 2. Web portal (new terminal)
cd web && npm install && npm run dev     # http://localhost:5173/building-violations/  (proxies the API to :8000)
# 3. Mobile app (new terminal)
cd mobile && npm install --legacy-peer-deps && npx expo start   # scan the QR with Expo Go (SDK 57), or `npx expo run:ios` / `run:android`
# The server address can also be changed on the app's login screen ("Server … change").
```

Demo logins (OTP is `123456` in demo mode): JE `9000000001`, AE `9000000002`, JC `9000000003`,
JC clerk `9000000004`, XEN `9000000005`, field squad `9000000006`, Additional Commissioner
`9000000007`, module admin `9000000009`, Planning Branch `9000000011`, Revenue Branch `9000000012`,
Legal Branch `9000000013`, GIS lab `9000000014`.

## What is inside

* **Field app** - PID lookup (DULB API), auto-fill of owner/mobile/address, GPS fix and automatic
  government-land detection (point-in-polygon on uploaded GeoJSON layers), violation picker with the
  legal basis and evidence checklist, in-camera geotagged photos/videos, offline queue, delivery-proof
  and execution-proof capture with distance check from the property.
* **Workflow engine** - `backend/app/services/building_violations/workflow.py`: role-checked state
  machine with statutory minimum periods (3 days s.261, 7 days s.408A, 10 days HPPA, 30 days s.284),
  SLA timers and escalation, hash-chained audit trail, appeal/stay handling, JC-clerk sub-login.
* **Notices** - bilingual HTML → PDF with QR code, SHA-256 hash, PAdES digital signature (local
  certificate, USB token via PKCS#11, or Aadhaar eSign adapter), SMS (Pixabits / any DLT gateway) and
  optional WhatsApp (Aisensy) to the PID-linked and alternate numbers, public verification page,
  download/print, re-send.
* **Anti-spoofing** - every geotag is checked for mock-location apps, rooted phones, emulators,
  Developer options, VPN/proxy, stale fixes and impossible travel; hardware attestation
  (Play Integrity / App Attest) and IP intelligence are switched on by configuration.
* **Dashboards and reports** - KPI tiles, workflow funnel, zone/ward tables, violation mix, trends,
  ageing, SLA turnaround, officer performance, map, deadlines; 13 registers exportable to CSV/Excel.
* **Masters** - zones/wards/divisions, violation types, legal sections, order types, SLA config,
  sanctioned plans and licences (manual + bulk CSV/XLSX), government land layers, officers.
* **Branch referrals** - a case can be sent to the Planning, Revenue, Legal, Engineering or Fire branch
  (or any branch the admin adds) for a report; the branch sees the full history and answers in the
  system; a "hold" referral blocks the final order until answered.
* **Litigation** - appeals before the Divisional Commissioner, Commissioner, civil court, High Court,
  Supreme Court or NGT; stays are recorded only with the stay order uploaded; stay expiry reminders;
  litigation register.
* **Orders issued before the system** - the JC office records the backlog of paper demolition /
  sealing / eviction orders (single entry or register upload) and keeps their status current.
* **GIS-lab government-land database** - versioned layers uploaded as GeoJSON, KML/KMZ or zipped
  shapefile (EPSG:4326); parcels with open encroachment cases show red on the map.
* **Live enforcement map** - pins coloured by status; clicking a pin or a land parcel shows the case
  history; planned inspections shown as diamonds; refreshes every minute (web and app).
* **Planned inspections** - JC/AE push PIDs or map points to JEs, singly or in bulk (e.g. all PGs
  from the PID database); the app allows the inspection to start only within 100 m of the property
  (server-enforced geofence) and closes each task as violation recorded / no violation / not found.
* **Administration** - workflow rules (who may do what at each stage), routing switches, role
  permissions with per-officer overrides, jurisdictions (zones/wards/divisions/supervisor/branch),
  bulk re-assignment, SLA and order periods, branches - all data-driven, every change logged with the
  authorising order.

See `docs/02-INTEGRATION-GUIDE.md` for the exact steps to mount the module inside the existing
MCG platform backend and portal, and the MCG HARYANA app.

**Configurable review hierarchy** (12 Sep 2026): Administration → Hierarchy lets the admin rename JE / AE / JC, add or remove reviewer stages and create roles; the portal and the field app relabel themselves from `/masters/workflow-config/`.
