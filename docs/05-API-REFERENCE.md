# 05 - API reference

Full OpenAPI 3 schema: `docs/openapi.yaml` (regenerate with `python manage.py spectacular --file
docs/openapi.yaml`; interactive docs at `/api/docs/` when running standalone).

Base path: `/building-violations/api/` · Auth: `Authorization: Bearer <access_token>` · Errors:
`{"detail": "..."}` · Lists: `{count,next,previous,results}` with `?page=&page_size=&search=&ordering=`.

| Method & path | Purpose |
|---|---|
| POST `auth/otp/request/` `{mobile}` · POST `auth/otp/verify/` `{mobile,otp}` | Standalone OTP login (not routed when `BVMS_USE_PLATFORM_AUTH=1`) |
| GET `users/me/` | Profile, role, zones, unread notifications |
| GET `masters/zones/` `wards/` `divisions/` `violation-types/` `legal-sections/` (`?statute=`) `order-types/` `sla/` | Masters (admin may POST/PATCH) |
| GET `masters/legal-sections/statutes/` · GET `masters/wards/geojson/` | Statute list · ward polygons |
| GET `property/pid/{pid}/` · GET `property/nearby/?lat&lng` | DULB PID lookup |
| GET `gis/check-point/?lat&lng` | Govt-land parcels containing the point + ward |
| GET `gis/govt-land/geojson/?bbox=` · POST `gis/land-layers/` (multipart GeoJSON) | Land layers |
| GET/POST `sanctioned-plans/` · GET `sanctioned-plans/by-pid/{pid}/` · POST `sanctioned-plans/bulk_upload/` · GET `sanctioned-plans/template/` | Sanctioned plans & licences |
| POST `media/` (multipart: file, kind, case?, notice?, latitude, longitude, accuracy_m, captured_at, device_id, caption) | Geotagged upload |
| GET `cases/?status=&zone=&ward=&land_type=&inbox=1&mine=1&overdue=1&search=` · GET `cases/counts/` | Case lists / badges |
| POST `cases/` | Create (JE); body = `CaseCreateSerializer` (violations[], media_ids[], submit) |
| GET/PATCH `cases/{id}/` · GET `cases/{id}/timeline/` · GET `cases/{id}/notices/` | Detail, audit chain |
| POST `cases/{id}/submit/` `ae_forward/` `ae_return/` `issue_notice/` `record_service/` `record_response/` `ae_forward_response/` `schedule_hearing/` `record_hearing/` `drop/` `record_appeal/` `decide_appeal/` `record_execution/` `close/` `reopen/` | Workflow actions (role-checked) |
| GET `notices/` · GET `notices/{id}/` · GET `notices/{id}/pdf/` · POST `notices/{id}/resend_sms/` · POST `notices/{id}/resign/` | Notice register, PDF, SMS, re-sign |
| GET `/building-violations/public/verify/{code}/?h=` | Public QR verification (no auth) |
| GET `dashboards/summary/ funnel/ by-area/ violation-mix/ ageing/ sla/ officers/ trends/ map/ deadlines/` (`?zone&ward&from&to&land_type`) | MIS |
| GET `reports/` · GET `reports/{name}/?export=csv|xlsx` | Registers: case-register, notice-register, order-register, execution-register, pendency, govt-land, sla-breach, sanctioned-plans |
| GET/POST/PATCH `officers/` · GET `officers/dropdown/?role=&zone=` | Officer directory (admin; JC may add clerks) |
| GET `notifications/` · POST `notifications/mark_read/` | In-app notifications |
| POST `cases/{id}/refer_branch/` `{branch, query, due_days, hold_case, assigned_to, media_ids}` · POST `cases/{id}/respond_branch/` `{referral, response, recommendation, media_ids}` · POST `cases/{id}/close_referral/` | Branch consultation |
| GET `referrals/?inbox=1&status=` · GET `referrals/counts/` | Referrals scoped to my branch / my referrals |
| POST `cases/{id}/record_appeal/` (authority, appeal_no, stay_granted, stay_order_media, stay_until, stay_scope, next_hearing_on ...) · POST `cases/{id}/decide_appeal/` (= `update_appeal/`: status, stay_until, next_hearing_on, stay_order_media, final_order_media, new_compliance_days ...) | Litigation flag; stay requires the uploaded order |
| POST `cases/{id}/reassign/` `{reported_by, assigned_ae, assigned_jc, order_reference}` · POST `admin/reassign-cases/` (by zone / ward / from_user / case_ids) | Re-assignment |
| GET/POST/PATCH `branches/` | Branch master |
| GET/PUT/POST(reset) `admin/workflow-rules/` · GET/PUT `admin/settings/` · GET/PUT `admin/permissions/` · GET/PUT `officers/{id}/permissions/` · GET `admin/audit-log/` | Administration (all writes take `order_reference`) |
| GET `reports/litigation-register/` · GET `reports/branch-referrals/` · GET `reports/planned-inspections/` | New registers |
| GET/POST `inspections/tasks/` (create: pid / address / latitude+longitude, category, instructions, assigned_to, due_days) · GET `inspections/tasks/counts/` · GET `inspections/tasks/geojson/` · GET `inspections/tasks/template/` · POST `inspections/tasks/bulk_upload/` (multipart file + title, category, instructions, due_days, assign_to, lookup_pid) | Planned inspections |
| POST `inspections/tasks/{id}/start/` `{latitude, longitude, accuracy_m}` (400 outside the geofence) · GET `inspections/tasks/{id}/distance/?lat&lng` · POST `.../close/` `{outcome, remarks, media_ids, latitude, longitude}` · POST `.../assign/` · POST `.../cancel/` · GET `inspections/batches/` | Field execution of pushed inspections |
| POST `cases/` with `task`, `inspector_latitude`, `inspector_longitude` | Case recorded from a pushed inspection (geofence enforced) |
| GET/POST `gis/land-layers/` (multipart: name, layer_key, agency, source, survey_date, source_file .geojson/.kml/.kmz/.zip) · DELETE `gis/land-layers/{id}/` (retire) · POST `gis/land-layers/{id}/reactivate/` | GIS-lab layer versions |
| GET `dashboards/map/?open=1&tasks=1` (pins with status + history) · GET `gis/govt-land/geojson/` (parcels with linked cases) | Live map |

### issue_notice body

```json
{"order_type": "SCN_261", "days": 7, "addressee_name": "Ramesh Kumar", "mobiles": ["98xxxxxxxx"],
 "hearing_at": "2026-09-25T11:00:00+05:30", "hearing_venue": "Office of the JC, Zone 2",
 "remarks": "reasons / operative text", "send_sms": true, "is_final_order": null}
```
`order_type` must be in the case's `available_order_types` (derived from the violations recorded);
`days` below the statutory minimum is rejected with 400.

### Location integrity (anti-GPS-spoofing)

| Endpoint | Purpose |
|---|---|
| `POST integrity/nonce/` → `{nonce, ttl_s}` | Single-use nonce the app binds into a Play Integrity / App Attest request |
| `POST integrity/precheck/` body `{latitude, longitude, accuracy_m, location_integrity}` → `{decision, reasons, flags, explanation, advice, …}` | Home-screen device check; never blocks, but is recorded |
| `GET integrity/checks/?decision=REJECTED&officer=&context=&platform=` · `GET integrity/checks/summary/` | Register of checks / 30-day counts, top reasons and repeat offenders (permission REPORTS_EXPORT) |
| `GET reports/location-integrity/?export=xlsx&decision=REJECTED` | Same data as a register export |

`location_integrity` is accepted (JSON, or a JSON string in multipart) by `POST media/`, `POST cases/` (with
`inspector_latitude/longitude`), `POST inspections/tasks/{id}/start/` and `…/close/`. Shape sent by the app:

```json
{"source": "app", "platform": "android", "native_module": true, "app_version": "1.0.0", "build_number": "12",
 "os_version": "15", "device_model": "Pixel 8", "device_id": "…", "is_physical_device": true, "rooted": false,
 "developer_options": false, "mock_location": false, "mock_apps_installed": [], "vpn_active": false,
 "proxy_configured": false, "simulated_by_software": null, "produced_by_accessory": null, "provider": "fused",
 "speed_mps": 0.3, "heading": 120, "fix_at": "2026-09-11T06:30:00Z", "fix_age_s": 1.8, "jitter_m": 0.6,
 "attestation": {"type": "play_integrity", "token": "…", "nonce": "…"}}
```
A REJECTED evaluation answers `400 {"detail": "Location integrity check failed: <reasons>. …"}` and nothing is stored as
evidence; the attempt itself is kept in `integrity/checks/`. Responses of `media/` carry `integrity_status`
(PASS | FLAGGED | UNVERIFIED) and `integrity_reasons`; case detail carries `inspector_integrity`; tasks `start_integrity`.

### Orders issued before the system (paper orders)

| Endpoint | Purpose |
|---|---|
| `POST legacy-orders/` (LegacyOrderSerializer: order_no, order_date, order_type, issued_by_name/designation, pid or address, ward_number, owner…, violations[], compliance_days, served_on, served_mode, current_status, executed_on, execution_action/mode, cost_incurred_inr, appeal_authority, appeal_no, stay_granted, stay_until, closed_on, legacy_reference, media_ids, order_reference) | Record one paper order → case detail (permission LEGACY_ORDERS_MANAGE) |
| `POST legacy-orders/bulk/` multipart {file (CSV/XLSX), title, order_reference} → batch {imported, errors[]} · `GET legacy-orders/template/` | Register import |
| `GET legacy-orders/?status=&ward=&search=` · `GET legacy-orders/summary/` · `GET legacy-orders/batches/` | Register of imported orders (jurisdiction-scoped), counts, upload history |
| `POST legacy-orders/{case_id}/status/` {status, on_date, remarks, order_reference, served_mode, execution_action, execution_mode, cost_incurred_inr, appeal_authority, appeal_no, stay_until, closure_reason, media_ids} | Record a historical status change from the paper file |
| `GET reports/legacy-orders/?export=xlsx` | Register export |

Imported cases carry `source = "LEGACY_ORDER"` and `legacy_reference`; their order carries `is_legacy = true`
(no `pdf_url`; the scanned copy is media of kind `LEGACY_ORDER`).
