# 09 - Security notes

1. **PID API credentials must live only on the server.** This module calls the DULB property API from
   `integrations/pid.py` with credentials taken from environment variables; they must never be placed in
   client-side JavaScript or mobile bundles. The platform team should verify that all existing PID calls
   are routed through the backend and rotate any credential that has ever shipped in a client bundle.
2. **Evidence integrity.** SHA-256 per file, distance-from-case check, hash-chained `CaseEvent`
   ledger (`verify_chain`), PAdES-signed PDFs with document hash in the QR. Evidence cannot be deleted
   after submission; edits are events.
3. **Access control.** Every workflow action re-checks role and status server-side (`_authorize`,
   `_require_status` in `app/services/building_violations/workflow.py`); jurisdiction scoping in
   `app/repositories/building_violations.py`; permissions are data-driven (docs/03).
4. **Personal data (DPDP Act, 2023).** Notices carry only the data required by law; the public
   verification page exposes notice number, property, addressee name and status - no mobile numbers.
   Signed PDFs are streamed behind auth by `notices/{id}/pdf/`; keep the S3 bucket private (or `/uploads/bvms/notices/`
   `internal` in nginx) if PDFs must not be fetched by URL.
5. **OTP.** Standalone mode hashes OTPs, limits attempts (5) and validity (10 min); DEBUG uses a fixed
   demo code - never enable DEBUG in production.
6. **Signing keys.** `backend/app/keys/*.p12` is git-ignored; use the platform's secret store.
8. **Tokens.** Stateless JWT (HS256 by default, `ALGORITHM`), access 12 h / refresh 30 days, user UUID in `sub`;
   rotate `SECRET_KEY` to invalidate every session. Inside the platform the platform's own JWT service is used.
7. **Uploads.** File types are whitelisted (images, video, PDF, DOC/XLS); size limit 200 MB; consider
   AV scanning at the reverse proxy.

## Location integrity (anti-GPS-spoofing)

Field evidence is only as good as the location attached to it. Mock-location apps (FlyGPS, Fake GPS Location …),
computer-tethered location simulation on iOS, rooted phones, emulators and VPN/proxy tricks are therefore treated as
first-class threats. The design is *defence in depth*: nothing the phone says is trusted on its own, and the server
keeps a record of every attempt.

### Layers

| Layer | Where | What it catches |
|---|---|---|
| 1. Device signals with every fix | app `src/services/integrity.ts` + native module `mobile/modules/location-integrity` | Android mock provider (`Location.isMock`), installed mock-location apps, Developer options, root/jailbreak, emulator/simulator, VPN transport / system proxy, iOS `CLLocationSourceInformation.isSimulatedBySoftware` (iOS 15+), fix age, accuracy radius, jitter between two consecutive fixes |
| 2. On-device refusal | app | Unambiguous spoofing (mock provider, simulated location, root, emulator) is refused before anything is sent, with a clear message |
| 3. Server evaluation | `services/location_integrity.py` `evaluate()` | Applies the admin's rules (below) to the signals, verifies attestation, runs the server-only checks, stores a `LocationIntegrityCheck`, and raises HTTP 400 on REJECTED so nothing is stored as evidence |
| 4. Hardware attestation | `services/attestation.py` | Google Play Integrity (Android) / Apple App Attest (iOS) verdicts bound to a single-use server nonce: genuine, unmodified app on an untampered device |
| 5. Server-only checks | `evaluate()` | Teleport detection (implied speed between the officer's consecutive *app* fixes, by fix time so offline uploads do not trip it), HTTP proxy headers, optional IP intelligence (VPN / proxy / Tor / hosting flags, IP-vs-GPS distance) |
| 6. Record & review | `LocationIntegrityCheck`, report `location-integrity`, dashboard KPI "GPS spoofing blocked", supervisor notification | Every PASS / FLAGGED / REJECTED with all signals, device, IP and travel speed; rejections notify the officer's reporting officer |

Enforcement points: evidence upload (`POST media/`), inspection recorded from a task (`POST cases/` inspector position),
planned inspection start / close (`inspections/tasks/{id}/start|close/`), and the app's home-screen pre-check
(`POST integrity/precheck/`, informational). Each `MediaAttachment` carries `integrity_status` + reasons; each case
exposes `inspector_integrity`; each task `start_integrity`.

### Admin switches (WorkflowSetting group "Location integrity")

| Setting | Default | Effect |
|---|---|---|
| block_mock_location | on | mock provider / software-simulated location → REJECT |
| block_rooted_devices | on | root / jailbreak → REJECT |
| block_emulators | on | emulator / simulator → REJECT |
| block_developer_options | on | Android Developer options enabled → REJECT (mock apps need them) |
| block_vpn_or_proxy | on | VPN or system proxy on the device, or VPN/proxy/Tor IP (with IP intelligence) → REJECT |
| block_web_geotags | **off in sandbox** | geotagged field evidence from a browser → REJECT (turn on in production; browser locations cannot be verified) |
| require_native_integrity_module | **off in sandbox** | builds without the native module (Expo Go, web) → REJECT (turn on once the production app is distributed) |
| require_device_attestation | **off in sandbox** | Play Integrity / App Attest verdict mandatory (turn on after the keys below are configured) |
| max_location_age_s | 120 | older fix at capture → REJECT |
| max_location_accuracy_m | 100 | wider accuracy radius → FLAG |
| max_plausible_speed_kmph | 200 | faster implied travel (> 1 km apart) → REJECT |
| ip_geo_max_distance_km | 500 | IP geolocates farther from the GPS → FLAG (0 disables) |

Anything switched off downgrades the signal from REJECT to FLAG - it is still recorded and visible to supervisors.

### Production configuration

| Variable | Purpose |
|---|---|
| `BVMS_IP_INTEL_URL` | IP-intelligence endpoint with `{ip}` placeholder (e.g. `https://ipinfo.io/{ip}?token=…` with the privacy add-on). Empty = IP checks off. |
| `BVMS_TRUSTED_PROXY_HOPS` | Number of `X-Forwarded-For` entries added by MCG's own proxies (default 1) |
| `BVMS_PLAY_INTEGRITY_SA_JSON`, `BVMS_ANDROID_PACKAGE`, `BVMS_PLAY_INTEGRITY_REQUIRE_PLAY_RECOGNIZED` | Google service-account key with the Play Integrity API enabled and the app linked in Play Console; the app config needs `extra.playIntegrityCloudProjectNumber` |
| `BVMS_APP_ATTEST_ROOT_CA`, `BVMS_APPLE_TEAM_ID`, `BVMS_IOS_BUNDLE_ID`, `BVMS_APP_ATTEST_ENV` | Apple App Attest: root CA PEM from apple.com/certificateauthority, Team ID, bundle id, `production` or `development` |

Recommended go-live order: distribute the EAS build (native module included) → turn on `require_native_integrity_module`
and `block_web_geotags` → configure Play Integrity / App Attest → turn on `require_device_attestation` → configure IP
intelligence.

### Limits, stated plainly

* The native module (Kotlin / Swift) is compiled by EAS / Xcode / Gradle, not in this repository's test run; test it on
  real devices (UAT scenarios 37-41) before turning the "require" switches on.
* `QUERY_ALL_PACKAGES` (listing installed mock-location apps) is restricted on Google Play to apps whose core purpose
  needs it; distribute through the managed / internal track or drop that permission (per-fix mock detection still works).
* A determined attacker with a rooted phone and a hooking framework can hide device signals - that is exactly why
  attestation and the server-only checks exist. With attestation required, spoofing needs a compromised device that
  still passes Play Integrity / App Attest, which is not a realistic threat for this system.
* VPNs do not change GPS; they are blocked because they hide the network origin and are commonly used together with
  spoofing tools. Officers on official corporate VPNs should capture evidence with the VPN off.
