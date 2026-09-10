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
| GET `reports/litigation-register/` · GET `reports/branch-referrals/` | New registers |

### issue_notice body

```json
{"order_type": "SCN_261", "days": 7, "addressee_name": "Ramesh Kumar", "mobiles": ["98xxxxxxxx"],
 "hearing_at": "2026-09-25T11:00:00+05:30", "hearing_venue": "Office of the JC, Zone 2",
 "remarks": "reasons / operative text", "send_sms": true, "is_final_order": null}
```
`order_type` must be in the case's `available_order_types` (derived from the violations recorded);
`days` below the statutory minimum is rejected with 400.
