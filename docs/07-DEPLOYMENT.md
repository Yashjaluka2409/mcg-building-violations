# 07 - Deployment

## Standalone (UAT server)

```
Ubuntu 22.04/24.04, Python 3.12, Node 20+, PostgreSQL 15+, Redis (for Celery), Nginx
apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2 fonts-noto-core     # WeasyPrint / Hindi
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env    # set DATABASE_URL, SECRET_KEY, PUBLIC_VERIFY_BASE, SMS_*, SIGNER_*, PID_*
python manage.py migrate && python manage.py load_legal_catalogue && python manage.py collectstatic
gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 4 --timeout 120
celery -A config worker -l info &   ;   celery -A config beat -l info &
cd ../web && npm ci && VITE_API_BASE=https://<host>/building-violations/api VITE_BASE_PATH=/building-violations/ npm run build
```

Nginx: serve `web/dist` at `/building-violations/` (SPA fallback to `index.html`), proxy
`/building-violations/api/`, `/building-violations/public/`, `/admin/` to gunicorn, `/media/` from
`MEDIA_ROOT` (protect `/media/bvms/notices/` with `internal` + X-Accel if signed PDFs must not be
public; the API's `notices/{id}/pdf/` streams them with auth).

Uploads: set `client_max_body_size 200m` (videos). Backups: PostgreSQL + `MEDIA_ROOT/bvms`.

## Inside the platform

Follow `02-INTEGRATION-GUIDE.md`; nothing else is deployed separately - the module rides on the
platform's gunicorn/celery/nginx and the portal's build.

## Mobile builds

```
cd mobile && npm install --legacy-peer-deps
npx expo prebuild                       # generates ios/ and android/ native projects
eas build -p android --profile uat      # or: npx expo run:android (local SDK)
eas build -p ios --profile uat          # requires Apple Developer account of MCG
```
Set `EXPO_PUBLIC_API_BASE` per profile in `eas.json`. Bundle ids: `in.gov.mcg.buildingviolations`
(change to the MCG HARYANA app's ids when merged into that app).

## Certificates for digital signing

* UAT: a self-signed PKCS#12 is generated automatically at `building_violations/keys/dev-signer.p12`.
* Production options (CCA framework):
  1. **Organisational Document Signer Certificate** (Class-3, issued to "Municipal Corporation
     Gurugram") installed on the signing server → `SIGNER=local`. Recommended for bulk, unattended signing.
  2. **Officer's USB DSC token** on the signing host → `SIGNER=pkcs11` with the token's PKCS#11 library.
  3. **Aadhaar eSign** via an empanelled ASP → `SIGNER=esign` (implement `ESignSigner.sign`).
* A timestamp authority URL (`SIGNER_TSA_URL`) may be added for long-term validation (LTV).

## Environment variables

See `backend/.env.example` - every setting is documented inline.
