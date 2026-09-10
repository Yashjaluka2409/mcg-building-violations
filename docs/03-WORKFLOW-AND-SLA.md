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
