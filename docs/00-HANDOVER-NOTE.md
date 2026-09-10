# Handover note for the MCG IT team (Austere Systems)

**Subject:** Building Violation Management System (BVMS) - code handover and sandbox deployment request

Dear team,

The Building Violation Management System has been developed as a pluggable module for the MCG platform
(same stack and design as the Sanitary Monitoring System: React + Vite + Tailwind portal, Django-style REST
backend, React Native / Expo mobile app). The complete source, documentation and a one-command sandbox are in
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
| UAT scenarios (36) | `docs/08-UAT-TEST-PLAN.md` |
| Security notes (incl. the PID credential exposure in the current portal bundle) | `docs/09-SECURITY-NOTES.md` |
| Sample signed notice | `docs/samples/` |

Automated tests: `cd backend && python manage.py test building_violations` (15 tests).

Please raise questions as GitHub issues on the repository so that they are tracked in one place.

Regards,
Yash Jaluka, Additional Commissioner, MCG
