# 07 - Deployment

## Sandbox / demo in one command

`./sandbox/run_sandbox.sh [--tunnel]` (see `sandbox/README.md`) builds the portal, seeds demo data and serves
everything from Django on one port; `--tunnel` adds a public Cloudflare quick-tunnel URL for demos.
`docker compose -f sandbox/docker-compose.yml up -d --build` does the same in a container with PostgreSQL.
Set `SERVE_SPA=1` + `DEMO_MODE=1` for sandboxes only.

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

### Location-integrity variables (see docs/09-SECURITY-NOTES.md)

`BVMS_IP_INTEL_URL`, `BVMS_TRUSTED_PROXY_HOPS`, `BVMS_PLAY_INTEGRITY_SA_JSON`, `BVMS_ANDROID_PACKAGE`,
`BVMS_PLAY_INTEGRITY_REQUIRE_PLAY_RECOGNIZED`, `BVMS_APP_ATTEST_ROOT_CA`, `BVMS_APPLE_TEAM_ID`, `BVMS_IOS_BUNDLE_ID`,
`BVMS_APP_ATTEST_ENV`. The mobile app needs an EAS / native build for the anti-spoofing module in
`mobile/modules/location-integrity` (autolinked); set `extra.playIntegrityCloudProjectNumber` in `app.json`.
Expo Go runs the app with JavaScript-only checks and is refused once `require_native_integrity_module` is on.

### Building the native apps locally (verified 11 Sep 2026 on macOS 26 / Xcode 26.6)

* `cd mobile && npx expo prebuild` generates `ios/` and `android/` (git-ignored; regenerate after config changes).
* iOS: CocoaPods needs a UTF-8 locale (`export LANG=en_US.UTF-8`). Three upstream scripts break on **spaces in the
  project path** - the Expo Constants pod script phase, its `get-app-config-ios.sh` (unquoted `$PROJECT_DIR`, which silently
  leaves the app without its manifest) and the "Bundle React Native code and images" phase; keep
  the checkout in a path without spaces (recommended) or quote the script paths as done in this sandbox.
  Build: `xcodebuild -workspace ios/MCGBuildingViolations.xcworkspace -scheme MCGBuildingViolations -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator'`.
* Android: JDK 17 (`brew install openjdk@17`), Android SDK with platform 35/36 (Gradle downloads the NDK itself);
  `cd android && ./gradlew :app:assembleDebug -PreactNativeArchitectures=arm64-v8a` → `app/build/outputs/apk/debug/app-debug.apk`.
  The Kotlin anti-spoofing module (`modules/location-integrity`) compiles with two deprecation warnings only.
* Both debug builds load JavaScript from the Metro server (`npx expo start`); point the app at the API through the
  login screen ("Server … change"): Android emulator `http://10.0.2.2:8000`, iOS simulator `http://127.0.0.1:8000`.
