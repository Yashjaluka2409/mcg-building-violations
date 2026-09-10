# 06 - Database Schema

All tables are prefixed `bvms_`. Generated from `backend/building_violations/models.py` (Django ORM); the same DDL is produced by `manage.py migrate` on PostgreSQL or SQLite.


## `bvms_zone` - Zone

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| code | CharField | no |  |
| name_en | CharField | no |  |
| name_hi | CharField | no |  |
| active | BooleanField | no |  |

## `bvms_division` - Division

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| code | CharField | no |  |
| zone_id | FK → bvms_zone | no |  |
| name_en | CharField | no |  |
| active | BooleanField | no |  |

## `bvms_ward` - Ward

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| number | PositiveSmallIntegerField | no |  |
| name_en | CharField | no |  |
| name_hi | CharField | no |  |
| zone_id | FK → bvms_zone | no |  |
| division_id | FK → bvms_division | yes |  |
| boundary | JSONField | yes | GeoJSON Polygon/MultiPolygon (WGS84) |
| active | BooleanField | no |  |

## `bvms_branch` - Branch

A branch of the Corporation that can be consulted on a case (Planning, Revenue, Legal, Fire ...).

| Column | Type | Null | Description |
|---|---|---|---|
| code | CharField | no |  |
| name_en | CharField | no |  |
| name_hi | CharField | no |  |
| description | TextField | no |  |
| head_designation | CharField | no |  |
| default_response_days | PositiveSmallIntegerField | no |  |
| active | BooleanField | no |  |

## `bvms_officer_profile` - OfficerProfile

Role and jurisdiction of a platform user inside this module.

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| user_id | FK → auth_user | no |  |
| role | CharField | no | choices: JE, AE, XEN, JC, JC_CLERK, ADDL_COMMISSIONER, COMMISSIONER, FIELD_STAFF, BRANCH_OFFICER, GIS_LAB, ADMIN, VIEWER |
| designation | CharField | no |  |
| employee_code | CharField | no |  |
| mobile | CharField | no |  |
| email | CharField | no |  |
| reports_to_id | FK → bvms_officer_profile | yes |  |
| delegation_order_no | CharField | no |  |
| delegation_order_date | DateField | yes |  |
| signature_image | FileField | yes |  |
| parent_profile_id | FK → bvms_officer_profile | yes | For JC_CLERK: the JC whose office this clerk belongs to |
| branch_id | FK → bvms_branch | yes | For BRANCH_OFFICER: the branch this officer answers for |
| active | BooleanField | no |  |
| zones | ManyToManyField | no |  |
| wards | ManyToManyField | no |  |
| divisions | ManyToManyField | no |  |
| (zones) | M2M → bvms_zone | | via `bvms_officer_profile_zones` |
| (wards) | M2M → bvms_ward | | via `bvms_officer_profile_wards` |
| (divisions) | M2M → bvms_division | | via `bvms_officer_profile_divisions` |

## `bvms_legal_statute` - LegalStatute

| Column | Type | Null | Description |
|---|---|---|---|
| code | CharField | no |  |
| title | CharField | no |  |
| citation | CharField | no |  |
| jurisdiction | CharField | no |  |
| primary | BooleanField | no |  |

## `bvms_legal_section` - LegalSection

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| statute_id | FK → bvms_legal_statute | no |  |
| section | CharField | no |  |
| heading | CharField | no |  |
| kind | CharField | no |  |
| text | TextField | no |  |
| schedule_fine_inr | PositiveIntegerField | yes |  |
| schedule_daily_fine_inr | PositiveIntegerField | yes |  |
| verify | BooleanField | no | Text extracted from scan - to be verified against Gazette |
| notes | TextField | no |  |

## `bvms_violation_type` - ViolationType

| Column | Type | Null | Description |
|---|---|---|---|
| code | CharField | no |  |
| category | CharField | no | choices: GOVT_LAND, PRIVATE_LAND_NO_SANCTION, DEVIATION_FROM_SANCTION, STREET_ENCROACHMENT, MISUSE_CHANGE_OF_USE, DANGEROUS_UNFIT, PROCEDURAL_NON_COMPLIANCE |
| title_en | CharField | no |  |
| title_hi | CharField | no |  |
| description | TextField | no |  |
| contravention_of | TextField | no | Phrase printed in the notice |
| legal_basis | JSONField | no |  |
| action_path | CharField | no |  |
| orders_available | JSONField | no |  |
| scn_response_days_default | PositiveSmallIntegerField | no |  |
| order_compliance_days_default | PositiveSmallIntegerField | no |  |
| statutory_minimum_days | PositiveSmallIntegerField | no |  |
| severity | CharField | no |  |
| compoundable | CharField | no |  |
| evidence_checklist | JSONField | no |  |
| schedule_fine_inr | PositiveIntegerField | yes |  |
| schedule_daily_fine_inr | PositiveIntegerField | yes |  |
| appeal | TextField | no |  |
| notes | TextField | no |  |
| active | BooleanField | no |  |
| sort_order | PositiveSmallIntegerField | no |  |

## `bvms_order_type` - OrderType

| Column | Type | Null | Description |
|---|---|---|---|
| code | CharField | no |  |
| title_en | CharField | no |  |
| title_hi | CharField | no |  |
| statute | CharField | no |  |
| section | CharField | no |  |
| kind | CharField | no |  |
| min_days | PositiveSmallIntegerField | no |  |
| default_days | PositiveSmallIntegerField | no |  |
| template | CharField | no |  |
| appeal_days | PositiveSmallIntegerField | yes |  |
| appeal_to | CharField | no |  |
| body_override_en | TextField | no | Admin-editable operative text (optional) |
| body_override_hi | TextField | no |  |
| active | BooleanField | no |  |

## `bvms_sla_config` - SLAConfig

Turn-around time per workflow stage; escalation goes to `escalate_to_role`.

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| stage | CharField | no |  |
| label | CharField | no |  |
| hours | PositiveIntegerField | no |  |
| escalate_to_role | CharField | no | choices: JE, AE, XEN, JC, JC_CLERK, ADDL_COMMISSIONER, COMMISSIONER, FIELD_STAFF, BRANCH_OFFICER, GIS_LAB, ADMIN, VIEWER |
| active | BooleanField | no |  |

## `bvms_land_layer_upload` - LandLayerUpload

One upload of a government-land layer by the GIS lab (GeoJSON / KML / zipped shapefile, WGS84).

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| name | CharField | no |  |
| layer_key | SlugField | no | Stable id of the layer, e.g. mcg-green-belts; re-uploads with the same key replace the old version |
| version | PositiveIntegerField | no |  |
| replaces_id | FK → bvms_land_layer_upload | yes |  |
| agency | CharField | no | choices: MCG, HSVP, GMDA, STATE_GOVT, PWD, IRRIGATION, FOREST, PANCHAYAT, RAILWAYS, NHAI, DEFENCE, OTHER |
| source_file | FileField | no |  |
| file_format | CharField | no | choices: GEOJSON, KML, SHP_ZIP |
| source | CharField | no | Revenue record / survey / drone / DTP layout ... |
| survey_date | DateField | yes |  |
| feature_count | PositiveIntegerField | no |  |
| skipped_count | PositiveIntegerField | no |  |
| uploaded_by_id | FK → auth_user | yes |  |
| remarks | TextField | no |  |
| active | BooleanField | no |  |
| import_log | TextField | no |  |

## `bvms_govt_land_parcel` - GovtLandParcel

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| name | CharField | no |  |
| agency | CharField | no | choices: MCG, HSVP, GMDA, STATE_GOVT, PWD, IRRIGATION, FOREST, PANCHAYAT, RAILWAYS, NHAI, DEFENCE, OTHER |
| land_use | CharField | no |  |
| village | CharField | no |  |
| khasra_no | CharField | no |  |
| area_sqm | DecimalField | yes |  |
| ward_id | FK → bvms_ward | yes |  |
| geometry | JSONField | no | GeoJSON Polygon / MultiPolygon (WGS84) |
| bbox | JSONField | no | [minx, miny, maxx, maxy] for quick filtering |
| properties | JSONField | no |  |
| layer_upload_id | FK → bvms_land_layer_upload | yes |  |
| layer_key | SlugField | no |  |
| active | BooleanField | no |  |

## `bvms_sanctioned_plan` - SanctionedPlan

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| plan_no | CharField | no |  |
| pid | CharField | no |  |
| address | TextField | no |  |
| ward_id | FK → bvms_ward | yes |  |
| zone_id | FK → bvms_zone | yes |  |
| latitude | DecimalField | yes |  |
| longitude | DecimalField | yes |  |
| owner_name | CharField | no |  |
| owner_mobile | CharField | no |  |
| plot_area_sqm | DecimalField | yes |  |
| land_use | CharField | no |  |
| building_type | CharField | no |  |
| sanctioned_on | DateField | no |  |
| valid_till | DateField | yes |  |
| sanction_mode | CharField | no |  |
| permitted_floors | CharField | no |  |
| permitted_ground_coverage_pct | DecimalField | yes |  |
| permitted_far | DecimalField | yes |  |
| permitted_height_m | DecimalField | yes |  |
| setbacks | JSONField | no |  |
| licence_no | CharField | no |  |
| licence_holder | CharField | no |  |
| licence_date | DateField | yes |  |
| licence_valid_till | DateField | yes |  |
| licence_authority | CharField | no |  |
| colony_name | CharField | no |  |
| architect_name | CharField | no |  |
| architect_registration_no | CharField | no |  |
| dpc_certificate_on | DateField | yes |  |
| occupation_certificate_no | CharField | no |  |
| occupation_certificate_on | DateField | yes |  |
| status | CharField | no |  |
| source | CharField | no | choices: MANUAL, BULK_UPLOAD, PLATFORM_SYNC |
| external_ref | CharField | no |  |
| remarks | TextField | no |  |
| created_by_id | FK → auth_user | yes |  |

## `bvms_media` - MediaAttachment

| Column | Type | Null | Description |
|---|---|---|---|
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| id | UUIDField | no |  |
| case_id | FK → bvms_case | yes |  |
| task_id | FK → bvms_inspection_task | yes |  |
| notice_id | FK → bvms_notice | yes |  |
| sanctioned_plan_id | FK → bvms_sanctioned_plan | yes |  |
| kind | CharField | no | choices: INSPECTION, NOTICE_DELIVERY, ORDER_DELIVERY, RESPONSE, HEARING, EXECUTION, COMPLIANCE, APPEAL, STAY_ORDER, COURT_ORDER, SANCTION_DOC, TASK_EVIDENCE, BRANCH_REFE |
| media_type | CharField | no |  |
| file | FileField | no |  |
| original_name | CharField | no |  |
| size_bytes | PositiveBigIntegerField | no |  |
| sha256 | CharField | no |  |
| latitude | DecimalField | yes |  |
| longitude | DecimalField | yes |  |
| accuracy_m | DecimalField | yes |  |
| altitude_m | DecimalField | yes |  |
| captured_at | DateTimeField | yes |  |
| device_id | CharField | no |  |
| distance_from_case_m | DecimalField | yes |  |
| geotag_verified | BooleanField | no |  |
| caption | CharField | no |  |
| uploaded_by_id | FK → auth_user | yes |  |

## `bvms_sequence` - Sequence

Atomic counters for case / notice numbering.

| Column | Type | Null | Description |
|---|---|---|---|
| key | CharField | no |  |
| value | PositiveIntegerField | no |  |

## `bvms_case` - ViolationCase

| Column | Type | Null | Description |
|---|---|---|---|
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| id | UUIDField | no |  |
| case_no | CharField | no |  |
| status | CharField | no | choices: DRAFT, PENDING_AE, RETURNED_TO_JE, PENDING_JC, SCN_ISSUED, SCN_SERVED, RESPONSE_RECEIVED, RESPONSE_PENDING_AE, RESPONSE_PENDING_JC, NO_RESPONSE, HEARING_SCHEDUL |
| status_changed_at | DateTimeField | no |  |
| source | CharField | no |  |
| complaint_ref | CharField | no |  |
| priority | CharField | no |  |
| pid | CharField | no | DULB Property ID |
| pid_snapshot | JSONField | no | Property record fetched from the PID API at creation |
| pid_linked_mobile | CharField | no |  |
| alternate_mobile | CharField | no |  |
| address_line | TextField | no |  |
| locality | CharField | no |  |
| sector | CharField | no |  |
| village_colony | CharField | no |  |
| pincode | CharField | no |  |
| ward_id | FK → bvms_ward | yes |  |
| zone_id | FK → bvms_zone | yes |  |
| division_id | FK → bvms_division | yes |  |
| latitude | DecimalField | yes |  |
| longitude | DecimalField | yes |  |
| location_accuracy_m | DecimalField | yes |  |
| land_type | CharField | no | choices: GOVT_MCG, GOVT_STATE, PRIVATE, UNKNOWN |
| govt_parcel_id | FK → bvms_govt_land_parcel | yes |  |
| sanctioned_plan_id | FK → bvms_sanctioned_plan | yes |  |
| owner_name | CharField | no |  |
| owner_father_name | CharField | no |  |
| occupier_name | CharField | no |  |
| builder_name | CharField | no |  |
| person_on_site | CharField | no |  |
| construction_stage | CharField | no | choices: PLINTH, UNDER_CONSTRUCTION, COMPLETED, OCCUPIED |
| plot_area_sqm | DecimalField | yes |  |
| covered_area_sqm | DecimalField | yes |  |
| storeys | CharField | no |  |
| height_m | DecimalField | yes |  |
| use_observed | CharField | no |  |
| description | TextField | no | Inspection report / observations |
| measurements | JSONField | no | Permitted vs actual values |
| reported_by_id | FK → auth_user | no |  |
| assigned_ae_id | FK → auth_user | yes |  |
| assigned_jc_id | FK → auth_user | yes |  |
| current_owner_role | CharField | no | choices: JE, AE, XEN, JC, JC_CLERK, ADDL_COMMISSIONER, COMMISSIONER, FIELD_STAFF, BRANCH_OFFICER, GIS_LAB, ADMIN, VIEWER |
| stage_due_at | DateTimeField | yes | SLA due time for the current stage |
| sla_breached | BooleanField | no |  |
| inspected_at | DateTimeField | no |  |
| submitted_at | DateTimeField | yes |  |
| ae_forwarded_at | DateTimeField | yes |  |
| jc_received_at | DateTimeField | yes |  |
| scn_issued_at | DateTimeField | yes |  |
| scn_served_at | DateTimeField | yes |  |
| response_due_at | DateTimeField | yes |  |
| response_received_at | DateTimeField | yes |  |
| hearing_at | DateTimeField | yes |  |
| decided_at | DateTimeField | yes |  |
| order_issued_at | DateTimeField | yes |  |
| order_served_at | DateTimeField | yes |  |
| compliance_due_at | DateTimeField | yes |  |
| executed_at | DateTimeField | yes |  |
| closed_at | DateTimeField | yes |  |
| task_id | FK → bvms_inspection_task | yes |  |
| inspector_latitude | DecimalField | yes | Officer's device location at the time of recording |
| inspector_longitude | DecimalField | yes |  |
| inspector_distance_m | DecimalField | yes |  |
| litigation_status | CharField | no |  |
| litigation_authority | CharField | no |  |
| stay_until | DateField | yes |  |
| next_hearing_on | DateField | yes |  |
| stop_work_issued | BooleanField | no |  |
| sealed | BooleanField | no |  |
| decision | CharField | no |  |
| decision_reasons | TextField | no |  |
| final_order_id | FK → bvms_notice | yes |  |
| closure_reason | TextField | no |  |
| demolition_cost_inr | DecimalField | yes |  |
| cost_recovery_status | CharField | no |  |

## `bvms_case_violation` - CaseViolation

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| case_id | FK → bvms_case | no |  |
| violation_type_id | FK → bvms_violation_type | no |  |
| details | JSONField | no | permitted / actual measurements, floors etc. |
| remarks | TextField | no |  |
| is_primary | BooleanField | no |  |

## `bvms_notice` - Notice

A show-cause notice, order, memo or referral generated for a case.

| Column | Type | Null | Description |
|---|---|---|---|
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| id | UUIDField | no |  |
| case_id | FK → bvms_case | no |  |
| order_type_id | FK → bvms_order_type | no |  |
| notice_no | CharField | no |  |
| kind | CharField | no |  |
| issued_by_id | FK → auth_user | no |  |
| issued_at | DateTimeField | no |  |
| addressee_name | CharField | no |  |
| addressee_address | TextField | no |  |
| addressee_mobiles | JSONField | no |  |
| response_days | PositiveSmallIntegerField | no |  |
| response_due_at | DateTimeField | yes |  |
| compliance_days | PositiveSmallIntegerField | no |  |
| compliance_due_at | DateTimeField | yes |  |
| hearing_at | DateTimeField | yes |  |
| hearing_venue | CharField | no |  |
| operative_text_en | TextField | no |  |
| operative_text_hi | TextField | no |  |
| html_snapshot | TextField | no |  |
| context_snapshot | JSONField | no |  |
| pdf | FileField | yes |  |
| signed_pdf | FileField | yes |  |
| document_hash | CharField | no |  |
| verification_code | CharField | no |  |
| qr_payload | TextField | no |  |
| signature_status | CharField | no | choices: UNSIGNED, SIGNED, FAILED |
| signer_name | CharField | no |  |
| signer_cert_subject | CharField | no |  |
| signer_cert_serial | CharField | no |  |
| signed_at | DateTimeField | yes |  |
| signature_error | TextField | no |  |
| served_at | DateTimeField | yes |  |
| served_mode | CharField | no | choices: SMS, IN_PERSON, AFFIXATION, POST, EMAIL, WHATSAPP, BEAT_OF_DRUM |
| served_by_id | FK → auth_user | yes |  |
| service_remarks | TextField | no |  |
| superseded_by_id | FK → bvms_notice | yes |  |
| is_final_order | BooleanField | no |  |

## `bvms_notice_dispatch` - NoticeDispatch

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| notice_id | FK → bvms_notice | no |  |
| channel | CharField | no |  |
| to | CharField | no |  |
| message | TextField | no |  |
| status | CharField | no |  |
| provider_ref | CharField | no |  |
| attempts | PositiveSmallIntegerField | no |  |
| last_error | TextField | no |  |
| sent_at | DateTimeField | yes |  |

## `bvms_case_response` - CaseResponse

Reply of the noticee to a show-cause notice.

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| case_id | FK → bvms_case | no |  |
| notice_id | FK → bvms_notice | yes |  |
| received_on | DateField | no |  |
| received_via | CharField | no | choices: JE, JC_CLERK, AE, JC, HEARING, POST |
| submitted_by_name | CharField | no |  |
| summary | TextField | no |  |
| requests_hearing | BooleanField | no |  |
| is_within_time | BooleanField | no |  |
| uploaded_by_id | FK → auth_user | no |  |
| ae_comments | TextField | no |  |
| ae_commented_at | DateTimeField | yes |  |
| jc_remarks | TextField | no |  |

## `bvms_hearing` - Hearing

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| case_id | FK → bvms_case | no |  |
| notice_id | FK → bvms_notice | yes |  |
| scheduled_at | DateTimeField | no |  |
| venue | CharField | no |  |
| presiding_id | FK → auth_user | no |  |
| held_at | DateTimeField | yes |  |
| attendees | TextField | no |  |
| proceedings | TextField | no |  |
| outcome | CharField | no |  |
| next_date | DateTimeField | yes |  |

## `bvms_appeal` - Appeal

An appeal / writ / suit against a notice or order, and the stay (if any) granted in it.

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| case_id | FK → bvms_case | no |  |
| order_id | FK → bvms_notice | yes |  |
| authority | CharField | no | choices: DIVISIONAL_COMMISSIONER, COMMISSIONER_MCG, CIVIL_COURT, HIGH_COURT, SUPREME_COURT, NGT, OTHER |
| authority_other | CharField | no |  |
| filed_on | DateField | no |  |
| appeal_no | CharField | no | Appeal / CWP / SLP / OA number |
| appellant_name | CharField | no |  |
| counsel_for_mcg | CharField | no |  |
| status | CharField | no | choices: PENDING, STAYED, STAY_VACATED, DISMISSED, ALLOWED, MODIFIED, WITHDRAWN, DISPOSED |
| stay_granted | BooleanField | no |  |
| stay_order_date | DateField | yes |  |
| stay_until | DateField | yes | Blank = until further orders / next date |
| stay_scope | CharField | no | choices: FULL, DEMOLITION_ONLY, STATUS_QUO, PARTIAL |
| stay_order_id | FK → bvms_media | yes | Uploaded copy of the stay / interim order |
| conditions | TextField | no |  |
| next_hearing_on | DateField | yes |  |
| decided_on | DateField | yes |  |
| decision_summary | TextField | no |  |
| final_order_id | FK → bvms_media | yes | Uploaded copy of the final order / judgment |
| recorded_by_id | FK → auth_user | no |  |

## `bvms_execution` - ExecutionRecord

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| case_id | FK → bvms_case | no |  |
| order_id | FK → bvms_notice | yes |  |
| action | CharField | no | choices: DEMOLITION, PARTIAL_DEMOLITION, SEALING, DESEALING, EVICTION, REMOVAL, ALTERATION |
| mode | CharField | no | choices: OWNER_SELF, CORPORATION |
| executed_on | DateTimeField | no |  |
| squad_incharge | CharField | no |  |
| police_assistance | BooleanField | no |  |
| police_station | CharField | no |  |
| duty_magistrate | CharField | no |  |
| machinery_used | CharField | no |  |
| area_demolished_sqm | DecimalField | yes |  |
| seal_memo_no | CharField | no |  |
| cost_incurred_inr | DecimalField | yes |  |
| remarks | TextField | no |  |
| recorded_by_id | FK → auth_user | no |  |
| verified_by_id | FK → auth_user | yes |  |
| verified_at | DateTimeField | yes |  |

## `bvms_case_event` - CaseEvent

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| case_id | FK → bvms_case | no |  |
| at | DateTimeField | no |  |
| actor_id | FK → auth_user | yes |  |
| actor_role | CharField | no |  |
| action | CharField | no |  |
| from_status | CharField | no |  |
| to_status | CharField | no |  |
| remarks | TextField | no |  |
| payload | JSONField | no |  |
| ip_address | GenericIPAddressField | yes |  |
| device_id | CharField | no |  |
| latitude | DecimalField | yes |  |
| longitude | DecimalField | yes |  |
| prev_hash | CharField | no |  |
| hash | CharField | no |  |

## `bvms_notification` - Notification

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| user_id | FK → auth_user | no |  |
| case_id | FK → bvms_case | yes |  |
| title | CharField | no |  |
| body | TextField | no |  |
| level | CharField | no |  |
| read_at | DateTimeField | yes |  |

## `bvms_otp` - OTPRequest

Standalone-mode OTP login (the platform's own OTP service is used when mounted inside sms-be).

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| mobile | CharField | no |  |
| code_hash | CharField | no |  |
| expires_at | DateTimeField | no |  |
| consumed | BooleanField | no |  |
| attempts | PositiveSmallIntegerField | no |  |
| created_at | DateTimeField | no |  |

## `bvms_branch_referral` - BranchReferral

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| case_id | FK → bvms_case | no |  |
| branch_id | FK → bvms_branch | no |  |
| referred_by_id | FK → auth_user | no |  |
| referred_at | DateTimeField | no |  |
| query | TextField | no | What the branch is asked to examine / report on |
| due_at | DateTimeField | yes |  |
| hold_case | BooleanField | no | If true, final orders are blocked until the branch responds (subject to workflow setting) |
| status | CharField | no | choices: PENDING, RESPONDED, CLOSED, WITHDRAWN |
| assigned_to_id | FK → auth_user | yes |  |
| response | TextField | no |  |
| recommendation | CharField | no |  |
| responded_by_id | FK → auth_user | yes |  |
| responded_at | DateTimeField | yes |  |
| closed_by_id | FK → auth_user | yes |  |
| closed_at | DateTimeField | yes |  |
| closing_remarks | TextField | no |  |

## `bvms_workflow_rule` - WorkflowRule

Which role may perform which action when a case is in a given status.

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| status | CharField | no |  |
| role | CharField | no | choices: JE, AE, XEN, JC, JC_CLERK, ADDL_COMMISSIONER, COMMISSIONER, FIELD_STAFF, BRANCH_OFFICER, GIS_LAB, ADMIN, VIEWER |
| action | CharField | no |  |
| allowed | BooleanField | no |  |
| updated_by_id | FK → auth_user | yes |  |
| updated_at | DateTimeField | no |  |

## `bvms_workflow_setting` - WorkflowSetting

Typed key/value settings that change the routing and guards of the workflow.

| Column | Type | Null | Description |
|---|---|---|---|
| key | CharField | no |  |
| value | JSONField | no |  |
| value_type | CharField | no |  |
| label | CharField | no |  |
| description | TextField | no |  |
| group | CharField | no |  |
| choices | JSONField | no |  |
| updated_by_id | FK → auth_user | yes |  |
| updated_at | DateTimeField | no |  |

## `bvms_role_permission` - RolePermission

Module-level permissions per role (view all zones, export reports, manage plans ...).

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| role | CharField | no | choices: JE, AE, XEN, JC, JC_CLERK, ADDL_COMMISSIONER, COMMISSIONER, FIELD_STAFF, BRANCH_OFFICER, GIS_LAB, ADMIN, VIEWER |
| permission | CharField | no |  |
| allowed | BooleanField | no |  |
| updated_by_id | FK → auth_user | yes |  |
| updated_at | DateTimeField | no |  |

## `bvms_officer_permission_override` - OfficerPermissionOverride

Grant or revoke a permission for one officer, over and above the role defaults.

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| profile_id | FK → bvms_officer_profile | no |  |
| permission | CharField | no |  |
| allowed | BooleanField | no |  |
| reason | CharField | no |  |
| order_reference | CharField | no | Office order / Commissioner's order authorising the change |
| updated_by_id | FK → auth_user | yes |  |
| updated_at | DateTimeField | no |  |

## `bvms_admin_audit_log` - AdminAuditLog

Every administrative change (officer, jurisdiction, rule, permission, setting, re-assignment).

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| at | DateTimeField | no |  |
| actor_id | FK → auth_user | yes |  |
| action | CharField | no |  |
| target_type | CharField | no |  |
| target_id | CharField | no |  |
| before | JSONField | no |  |
| after | JSONField | no |  |
| order_reference | CharField | no |  |
| remarks | TextField | no |  |
| ip_address | GenericIPAddressField | yes |  |

## `bvms_inspection_batch` - InspectionBatch

A bulk push of properties for verification, e.g. 'all PGs in the PID database, Zone 2'.

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| title | CharField | no |  |
| category | CharField | no |  |
| created_by_id | FK → auth_user | no |  |
| source_file | FileField | yes |  |
| instructions | TextField | no |  |
| due_at | DateTimeField | yes |  |
| total | PositiveIntegerField | no |  |
| errors | JSONField | no |  |

## `bvms_inspection_task` - InspectionTask

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigAutoField | no |  |
| created_at | DateTimeField | no |  |
| updated_at | DateTimeField | no |  |
| batch_id | FK → bvms_inspection_batch | yes |  |
| category | CharField | no | choices: VERIFICATION, PG_HOSTEL, COMPLAINT, DRONE_FLAG, COURT_DIRECTION, SANCTION_FOLLOWUP, GOVT_LAND, RE_INSPECTION, OTHER |
| pid | CharField | no |  |
| pid_snapshot | JSONField | no |  |
| address | TextField | no |  |
| owner_name | CharField | no |  |
| owner_mobile | CharField | no |  |
| latitude | DecimalField | yes |  |
| longitude | DecimalField | yes |  |
| ward_id | FK → bvms_ward | yes |  |
| zone_id | FK → bvms_zone | yes |  |
| instructions | TextField | no | What the field officer must check |
| priority | CharField | no |  |
| created_by_id | FK → auth_user | no |  |
| assigned_to_id | FK → auth_user | yes |  |
| assigned_at | DateTimeField | yes |  |
| due_at | DateTimeField | yes |  |
| status | CharField | no | choices: ASSIGNED, UNASSIGNED, IN_PROGRESS, VIOLATION_RECORDED, NO_VIOLATION, NOT_FOUND, CANCELLED |
| related_case_id | FK → bvms_case | yes | For re-inspection tasks |
| started_at | DateTimeField | yes |  |
| start_latitude | DecimalField | yes |  |
| start_longitude | DecimalField | yes |  |
| start_distance_m | DecimalField | yes |  |
| completed_at | DateTimeField | yes |  |
| outcome_remarks | TextField | no |  |
| geofence_m | PositiveIntegerField | no | Officer must be within this many metres of the point to start |