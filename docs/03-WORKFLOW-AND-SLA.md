# 03 - Workflow, statuses, timers and SLA

## Statuses

| Status | Owner | Entered by | Leaves via |
|---|---|---|---|
| DRAFT | JE | create | submit |
| PENDING_AE | AE | submit | ae_forward / ae_return |
| RETURNED_TO_JE | JE | ae_return | submit |
| PENDING_JC | JC | ae_forward | issue_notice (SCN) / issue_order / drop / regularise |
| SCN_ISSUED | JE / field | JC issues SCN | record_service |
| SCN_SERVED | JC (clock: reply due) | service recorded | record_response / deadline sweep → NO_RESPONSE / schedule_hearing / issue_order |
| RESPONSE_PENDING_AE | AE | reply uploaded by JE | ae_forward_response |
| RESPONSE_PENDING_JC | JC | reply uploaded by clerk/JC, or AE forwarded, or hearing held | issue_order / issue_notice / schedule_hearing / drop / regularise |
| NO_RESPONSE | JC | sweep after reply deadline | issue_order (ex parte) / record_response (late) / schedule_hearing |
| HEARING_SCHEDULED | JC | schedule_hearing | record_hearing |
| ORDER_ISSUED | JE / field | final order issued | record_service |
| ORDER_SERVED | field (clock: comply by) | order served | deadline sweep → EXECUTION_DUE / record_execution / record_appeal(stay) |
| APPEAL_STAY | JC | stay recorded | decide_appeal |
| EXECUTION_DUE | field squad | compliance period expired | record_execution |
| COMPLIED / EXECUTED | JC | execution recorded | close |
| CLOSED / DROPPED / REGULARISED | - | close / drop | reopen (JC, with reasons) |

Interim actions that do not change status: stop-work order (s.262), sealing order (s.263A),
memos (police requisition, watch deputation, referral to Collector/DTCP, execution memo, cost recovery),
adding evidence, recording an appeal without stay.

## Statutory clocks (enforced in `services/workflow.py` and `services/notices.py`)

| Document | Minimum | MCG default | Clock starts |
|---|---|---|---|
| SCN s.261 proviso | none (reasonable opportunity) | 7 days | service |
| SCN s.408A(1) | 7 days | 7 | service |
| Demolition order s.261(1) | 3 days | **15 days** (per MCG decision) | delivery of the order |
| Order s.408A(2) | 7 days | 7 | service |
| Sealing s.263A | - | - | appeal 7 days |
| Demolition order s.284(3) | 30 days to vacate | 30 | order |
| HPPA s.4 notice (Collector) | 10 days | 10 | issue |

`deadline_sweep` (hourly) moves SCN_SERVED → NO_RESPONSE and ORDER_SERVED → EXECUTION_DUE when the
clocks expire and notifies the JC / field squad. A stay in appeal pauses the clock; on dismissal the
JC can set a fresh compliance period (never below the statutory minimum).

## SLA (administrative) - `SLAConfig`, editable by the admin

| Stage | Default hours | Escalates to |
|---|---|---|
| PENDING_AE | 72 | XEN |
| RETURNED_TO_JE | 72 | AE |
| PENDING_JC | 120 | Additional Commissioner |
| SCN_ISSUED (service) | 72 | AE |
| RESPONSE_PENDING_AE | 48 | - |
| RESPONSE_PENDING_JC / RESPONSE_RECEIVED / NO_RESPONSE | 120 | Additional Commissioner |
| HEARING_SCHEDULED | 240 | - |
| ORDER_ISSUED (service) | 72 | AE |
| EXECUTION_DUE | 168 | JC |
| EXECUTED (verify & close) | 72 | - |

`sla_sweep` (15 min) marks `sla_breached`, writes an `SLA_BREACH` event and notifies the escalation
role of the zone. Breaches appear on the dashboard, the pendency report and as red badges.

## Role matrix (who can do what)

See `ACTION_MATRIX` in `services/workflow.py` - it is also what the UI uses to show buttons.
ADMIN / COMMISSIONER / ADDL_COMMISSIONER can perform any action. JC_CLERK can only upload replies,
fix/record hearings and record appeals for the JC's cases. FIELD_STAFF can serve notices and record
executions but cannot create or decide cases.

## Evidence rules

* Submission to AE requires ≥1 inspection photo/video.
* Affixation as a mode of service requires a geotagged photo within 150 m of the case point.
* Execution requires ≥1 geotagged photo/video within 150 m (owner self-compliance uses kind COMPLIANCE).
* Evidence cannot be deleted after the case leaves DRAFT; every file is SHA-256 hashed.


## Branch referrals (Planning / Revenue / Legal / Engineering / Fire)

* AE, XEN or JC (permission `BRANCH_REFER`) can **refer a case to a branch** at any time before closure:
  query, days to respond, optional "hold final order", optional specific officer, documents.
* The main workflow status is **not** changed. The referral is tracked separately (`bvms_branch_referral`)
  and shown as a badge on the case; a *hold* referral blocks demolition / sealing / eviction orders until
  answered (setting `block_final_order_on_pending_referral`).
* **Branch officers** (role `BRANCH_OFFICER`, one branch each) see only the cases referred to their branch,
  with the **complete history** (inspection, evidence, notices, replies, hearings, timeline), and respond with
  a recommendation (violation confirmed / no violation / regularisable / government land confirmed /
  ownership disputed / legal hold ...) and documents. Responses are events on the case and notify the
  referring officer and the JC.
* Branches are a master (Administration → Branches); the shipped ones are Planning, Revenue, Legal,
  Engineering and Fire. Report: `reports/branch-referrals`.

## Litigation flag and stays

* `record_appeal` records an appeal/writ before the **Divisional Commissioner** (s.261(2) / s.263A(4)),
  **Commissioner MCG** (s.408B), **civil court**, **High Court**, **Supreme Court**, **NGT** or another forum,
  with appeal number, appellant, MCG counsel, order appealed and next hearing date.
* A **stay** can be recorded only with the **stay / interim order uploaded** to the case file (setting
  `require_stay_order_upload`, default on) - so every deferred action has a legal backing. Scope can be
  full, demolition-only, status quo or partial; "till" date optional (until further orders).
* The case carries `litigation_status` (NONE / APPEAL_PENDING / STAYED / DECIDED), `litigation_authority`,
  `stay_until`, `next_hearing_on`; a stay moves the case to `APPEAL_STAY` and the field squad is warned.
* `update_appeal` records later events: stay extended (new date + order), stay vacated, dismissed, allowed
  (case closed), modified (fresh compliance period, never below the statutory minimum), next dates, final
  order / judgment upload.
* `stay_expiry_sweep` (part of the hourly deadline sweep) reminds the JC and JE `stay_expiry_reminder_days`
  before a dated stay expires and again after it has expired. Dashboard: stays by authority, stays expiring,
  court dates; report: `reports/litigation-register`.

## What the administrator can change without a code release

| Area | Where | Stored in |
|---|---|---|
| Who may do which action at which status (workflow rules) | Administration → Workflow rules | `bvms_workflow_rule` (seeded from `services/access.py`) |
| Routing & guards: AE stage on/off, JE replies via AE, auto-assignment, hold-referral blocking, evidence requirements, geotag tolerance, stay-order requirement, reminders | Administration → Routing & guards | `bvms_workflow_setting` |
| Role permissions (view all zones, export reports, manage plans, refer, respond ...) | Administration → Access control | `bvms_role_permission` |
| Per-officer overrides (grant / revoke one permission for one officer) | Officers → officer → Permissions | `bvms_officer_permission_override` |
| Jurisdiction: zones, wards, divisions, supervisor, branch, delegation order | Officers → officer → Jurisdiction | `bvms_officer_profile` |
| Bulk re-assignment of cases after transfers | Administration → Re-assign cases | case events `REASSIGNED` |
| SLA hours / escalation role; default notice & order periods | Administration → SLA & order periods | `bvms_sla_config`, `bvms_order_type` |
| Branches | Administration → Branches | `bvms_branch` |

Every administrative write requires an **office-order reference** and is written to `bvms_admin_audit_log`
(before/after, actor, IP). Statutory minimum periods cannot be lowered from the UI.


## Government-land database (GIS lab)

* Role `GIS_LAB` (permission `LAND_LAYERS_MANAGE`) uploads layers as **GeoJSON, KML/KMZ or zipped
  shapefile** in EPSG:4326 from Government land → *Upload / update a layer*. Attributes `name, land_use,
  village, khasra, area_sqm, agency` are read when present; projected (UTM) shapefiles are rejected with a
  message to re-export in WGS84.
* Layers are **versioned by `layer_key`**: uploading again with the same key creates v2 and retires v1's
  parcels (they remain in the database for the audit trail and can be reactivated). Every upload is logged in
  the admin audit log with the memo reference.
* Every inspection point, delivery photo and execution photo is tested against the active parcels
  (`gis/check-point`); cases inside a parcel are linked to it.

## Live enforcement map

* `dashboards/map` returns every case pin with its current status, flags (stop-work, sealed, stay) and the
  last N events (`map_history_events`, default 6) so that **clicking a pin shows the case history** in the
  pop-up with a link to the file; planned inspections are drawn as diamonds when `?tasks=1`.
* `gis/govt-land/geojson` returns, for each parcel, the cases linked to it (`case_count`, `open_case_count`,
  `cases[]`) - parcels with open encroachment cases are filled red and **clicking a polygon lists its cases**.
* The same pop-ups are rendered in the mobile app's map (Leaflet in a WebView) and refresh every minute.

## Planned inspections (JC pushes PIDs / map points to the field)

* Officers with `TASKS_ASSIGN` (JC, AE, XEN by default) push a property for verification: **one at a time**
  (PID lookup, address or a click on the map) or **in bulk** (CSV/XLSX of PIDs with the template columns -
  e.g. every PG in the PID database). Rows with only a PID are completed from the DULB record (owner, mobile,
  address, coordinates). Each row becomes an `InspectionTask` with category (PG / hostel, complaint, drone
  flag, court direction, sanction follow-up, government-land watch, re-inspection...), instructions, priority
  and due date, auto-assigned to the JE of the ward (`auto_assign_tasks_by_ward`) or a named officer.
* **Geofence.** The JE sees the task in the app with the distance to the property. *Start inspection* sends
  the phone's GPS fix; the server refuses it unless the officer is within `inspection_geofence_m`
  (default **100 m**, also stored per task). Recording the resulting case (`cases/` with `task` and
  `inspector_latitude/longitude`) and filing a *no violation / not traceable* report (mandatory geotagged
  photo) are checked the same way (`require_geofence_for_task_inspection`). The start fix and distance are
  stored on the task and the case (`inspector_distance_m`).
* Outcomes: `VIOLATION_RECORDED` (case created and linked), `NO_VIOLATION`, `NOT_FOUND`, `CANCELLED`.
  The pushing officer is notified of every outcome; the dashboard shows open / overdue / violation-found /
  clear counts; report `reports/planned-inspections`.
