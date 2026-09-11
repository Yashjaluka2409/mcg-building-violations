# 08 - UAT test plan

Automated: `cd backend && python manage.py test building_violations` (15 tests: full private-land
flow, Corporation-land s.408A flow, interim stop-work/sealing, API round-trip incl. PDF and QR, branch
referral with hold, admin rule switch-off, AE-stage setting, permission override, jurisdiction change +
bulk re-assignment, stay requiring uploaded order + clock resumption, geofenced planned inspections, bulk PID push, no-violation
closure with on-site photo, GIS-lab KML upload with versioning and projected-shapefile rejection, map payloads with status/history).

## Manual scenarios (with demo logins, OTP 123456)

| # | Scenario | Steps | Expected |
|---|---|---|---|
| 1 | JE records a violation with PID | App/portal → New inspection → PID GGN012345 → Fetch → violations DV-03, DV-04 → photo → Submit | Owner/mobile auto-filled, sanctioned plan shown, case in PENDING_AE, AE notified |
| 2 | Government land auto-detection | New inspection at 28.4700, 77.0455 (demo green belt) | Land type = MCG land, parcel named, GL-01 suggested |
| 3 | AE returns | AE inbox → case → Return to JE with reasons | Status RETURNED_TO_JE, JE notified, reasons in timeline |
| 4 | AE forwards | AE → Forward to JC with recommendation | PENDING_JC, JC notified |
| 5 | JC issues SCN | JC → Issue notice → SCN_261, 7 days, hearing date → Issue & sign | Notice numbered MCG/BV/SCN/…, PDF bilingual with QR, signed, SMS console line, status SCN_ISSUED |
| 6 | Statutory minimum | JC → SCN_408A with 3 days | Rejected: minimum 7 days |
| 7 | Delivery proof | Field → Record delivery → Affixation → photo far from site | Rejected (geotag mismatch); photo at site accepted, status SCN_SERVED, reply due date computed from service |
| 8 | Clerk uploads reply | Clerk login → Upload reply | RESPONSE_PENDING_JC directly (no AE hop) |
| 9 | JE uploads reply | JE → Upload reply | RESPONSE_PENDING_AE → AE comments → JC |
| 10 | No reply | Set reply due in the past (admin) → run `deadline_sweep` | NO_RESPONSE, JC notified |
| 11 | Hearing | JC → Fix hearing → Record hearing (HEARD) | RESPONSE_PENDING_JC with proceedings |
| 12 | Demolition order | JC → Pass final order → DEMOLITION_ORDER_261, 15 days, reasons | ORDER_ISSUED, decision DEMOLITION, PDF cites s.261(1)/(6), appeal to Divisional Commissioner |
| 13 | Order served, clock | Field → Record delivery (in person) | ORDER_SERVED, "Comply by" +15 days |
| 14 | Stay | JC → Record appeal (stay till date) | APPEAL_STAY; decide appeal DISMISSED → ORDER_SERVED with fresh period |
| 15 | Execution due | Expire compliance date → sweep | EXECUTION_DUE, squad notified |
| 16 | Execution proof | Field → Record demolition → 2 photos + video at site, cost 45,000 | EXECUTED, cost booked, recovery PENDING |
| 17 | Close | JC → Verify & close | CLOSED; audit chain intact |
| 18 | QR verification | Scan QR / open verify URL | Public page shows genuine, hash match, status |
| 19 | Sealing | JC → Issue notice → SEALING_263A (interim) | Case flagged Sealed; order PDF cites s.263A(2)-(4) |
| 20 | Dashboards & reports | Dashboard filters by zone; Reports → case-register → Excel | Numbers reconcile with case list; file downloads |
| 21 | Sanctioned plan bulk upload | Plans → template → fill 2 rows → upload | created/updated counts; auto-link on next inspection with that PID |
| 22 | Offline (app) | Airplane mode → New inspection → Submit | "Saved offline"; sync from Home uploads media then case |
| 23 | Refer to Revenue Branch | JC → case → Refer to branch → Revenue, hold final order | Badge "with Revenue Branch (holds order)"; Pass final order refused until answered |
| 24 | Branch responds | Login 9000000012 (Revenue) → Branch inbox → case → full history visible → Respond as branch | Referral RESPONDED, JC notified, final order now allowed |
| 25 | Planning officer isolation | Login 9000000011 → cases | Only cases referred to Planning are visible |
| 26 | Admin switches off an action | Login 9000000009 → Administration → Workflow rules → DRAFT: untick JE "Submit for review" → save with order no. | JE can no longer submit; audit log shows RULES_UPDATE with the order no. |
| 27 | Skip AE stage | Administration → Routing & guards → "AE review before JC" off | New submissions land with the JC directly |
| 28 | Per-officer override | Officers → JE → Permissions → grant REPORTS_EXPORT | JE sees Reports menu and can export |
| 29 | Jurisdiction change + re-assignment | Officers → AE → Jurisdiction → zones/wards; Administration → Re-assign cases → ward → new AE | Cases move; REASSIGNED events; audit log |
| 30 | High Court stay | JC → Litigation → Record appeal → High Court, stay ticked without order | Refused; upload stay order → case APPEAL_STAY, header shows STAY badge, field app warns |
| 31 | Stay expiry | Set stay till tomorrow → run deadline sweep | JC/JE reminded; update appeal "stay vacated" → compliance clock resumes |
| 32 | GIS lab uploads a layer | Login 9000000014 → Government land → upload .kml / .geojson / zipped .shp with layer key | Parcels appear; version increments on re-upload; UTM shapefile rejected with EPSG:4326 message |
| 33 | Map shows live status | Issue SCN on a case → Enforcement map | Pin colour changes; clicking the pin shows the history; clicking the green-belt polygon lists its cases |
| 34 | JC pushes PGs | Login 9000000003 → Planned inspections → Bulk push with the CSV template (PG_HOSTEL) | Tasks created, auto-assigned to the ward JE, JE notified |
| 35 | Geofence | JE app → Planned inspections → Start while > 100 m away | Refused with distance; within 100 m start succeeds and the inspection form opens prefilled |
| 36 | No violation on site | JE → task → No violation without photo | Refused; with geotagged photo the task closes NO_VIOLATION and the JC is notified |
| 37 | Mock GPS app (Android) | Install FlyGPS / Fake GPS, set a fake position, JE app → New inspection → capture photo | Refused on the device ("mock (fake) GPS app … is providing the location"); home screen shows "Evidence capture blocked"; server register shows a REJECTED row with reason MOCK_LOCATION; JE's AE receives a "Location integrity rejection" notification |
| 38 | Developer options / VPN | Enable Developer options or a VPN, then try to start a planned inspection | Server refuses with HTTP 400 naming the reason; switching them off and tapping Re-check on the home screen returns "Device trusted" |
| 39 | Rooted phone / emulator | Run the app on an emulator or rooted phone | Refused (EMULATOR / ROOTED_DEVICE); admin can downgrade to a flag in Admin → Location integrity for a test device |
| 40 | Teleport | Capture a photo, then within minutes upload another with a position > 200 km away (e.g. via the web portal with a different browser location, after turning "Reject geotagged field evidence from a browser" off) | Second capture rejected as IMPLAUSIBLE_TRAVEL only when both came from the app; browser positions are FLAGGED "browser location (unverified)" instead |
| 41 | Production switches | Admin turns on "Require the app's native anti-spoofing checks" and "Reject geotagged field evidence from a browser" | Expo Go build and browser uploads with a location are refused; the EAS build passes; report `location-integrity` and dashboard KPI "GPS spoofing blocked (30 d)" reflect every attempt |
