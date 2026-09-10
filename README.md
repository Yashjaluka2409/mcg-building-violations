# MCG Building Violation Management System (BVMS)

A complete, integration-ready module for the Municipal Corporation Gurugram IT platform that takes a
building violation from **field inspection → AE review → Joint Commissioner → show-cause notice
(digitally signed, QR-verified, SMS-delivered) → reply / hearing → demolition or sealing order → 15-day
compliance clock → geotagged proof of execution**, under the Haryana Municipal Corporation Act, 1994,
the Haryana Building Code, 2017 and the Haryana Public Premises Act, 1972.

| Part | Folder | Stack | Status |
|---|---|---|---|
| Backend / API | `backend/` | Django 5 + Django REST Framework, PostgreSQL (SQLite for demo), Celery, WeasyPrint, pyHanko (PAdES signatures) | Runs; 4 end-to-end tests pass |
| Web portal module | `web/` | React 18 + Vite + TypeScript + Tailwind (MCG platform theme tokens), Leaflet, Recharts, i18next (EN/HI) | Type-checks; verified in browser |
| Mobile app module (iOS + Android) | `mobile/` | React Native / Expo SDK 53, expo-router, expo-camera/location, SQLite offline queue, Leaflet-in-WebView | Type-checks; build with EAS |
| Legal catalogue | `shared/legal/` | 5 statutes, 125 sections, 36 violation types, 28 notice/order types (JSON, single source of truth) | Complete; "verify" flags for Legal Branch |
| Documentation | `docs/` | Architecture, integration guide, workflow/SLA, legal framework, API (OpenAPI), DB schema, deployment, UAT plan, security notes | Complete |

## Quick start (demo on one machine)

```bash
# 1. Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env
python manage.py migrate && python manage.py seed_demo --with-cases
python manage.py runserver 127.0.0.1:8000
# 2. Web portal (new terminal)
cd web && npm install && npm run dev            # http://localhost:5173/building-violations/
# 3. Mobile app (new terminal)
cd mobile && npm install && npx expo start      # scan the QR with Expo Go, or `npx expo run:ios` / `run:android`
```

Demo logins (OTP is `123456` in DEBUG mode): JE `9000000001`, AE `9000000002`, JC `9000000003`,
JC clerk `9000000004`, XEN `9000000005`, field squad `9000000006`, Additional Commissioner
`9000000007`, module admin `9000000009` (Django admin password `mcgadmin`), Planning Branch
`9000000011`, Revenue Branch `9000000012`, Legal Branch `9000000013`, GIS lab `9000000014`.

Hindi PDFs need Pango on the host (`brew install pango` on macOS, `apt install libpango-1.0-0
libpangoft2-1.0-0` on Ubuntu); without it the reportlab fallback produces English-only PDFs.

## What is inside

* **Field app** - PID lookup (DULB API), auto-fill of owner/mobile/address, GPS fix and automatic
  government-land detection (point-in-polygon on uploaded GeoJSON layers), violation picker with the
  legal basis and evidence checklist, in-camera geotagged photos/videos, offline queue, delivery-proof
  and execution-proof capture with distance check from the property.
* **Workflow engine** - `backend/building_violations/services/workflow.py`: role-checked state
  machine with statutory minimum periods (3 days s.261, 7 days s.408A, 10 days HPPA, 30 days s.284),
  SLA timers and escalation, hash-chained audit trail, appeal/stay handling, JC-clerk sub-login.
* **Notices** - bilingual HTML → PDF with QR code, SHA-256 hash, PAdES digital signature (local
  certificate, USB token via PKCS#11, or Aadhaar eSign adapter), SMS to the PID-linked and alternate
  numbers, public verification page, download/print, re-send.
* **Dashboards and reports** - KPI tiles, workflow funnel, zone/ward tables, violation mix, trends,
  ageing, SLA turnaround, officer performance, map, deadlines; 8 registers exportable to CSV/Excel.
* **Masters** - zones/wards/divisions, violation types, legal sections, order types, SLA config,
  sanctioned plans and licences (manual + bulk CSV/XLSX), government land layers, officers.
* **Branch referrals** - a case can be sent to the Planning, Revenue, Legal, Engineering or Fire branch
  (or any branch the admin adds) for a report; the branch sees the full history and answers in the
  system; a "hold" referral blocks the final order until answered.
* **Litigation** - appeals before the Divisional Commissioner, Commissioner, civil court, High Court,
  Supreme Court or NGT; stays are recorded only with the stay order uploaded; stay expiry reminders;
  litigation register.
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
MCG platform (sms-be / mcg-sms.austere.biz) and the MCG HARYANA app.
