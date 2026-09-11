# 06 - Database Schema

All module tables are prefixed `bvms_`; the standalone user registry is `users` (UUID primary key, like the platform's UserModel).
Generated from `backend/app/models/building_violations.py` (SQLAlchemy 2.0) by `backend/scripts/gen_schema_doc.py`; the same DDL
is produced by `python -m app.cli migrate` (Alembic) on PostgreSQL or SQLite. Geometry is GeoJSON in JSON columns (PostGIS optional).

## `bvms_branch` - Branch

| Column | Type | Null | Description |
|---|---|---|---|
| code | String(20) | no | primary key |
| name_en | String(120) | no |  |
| name_hi | String(120) | no |  |
| description | Text | no |  |
| head_designation | String(120) | no |  |
| default_response_days | Integer | no |  |
| active | Boolean | no |  |

## `bvms_legal_statute` - LegalStatute

| Column | Type | Null | Description |
|---|---|---|---|
| code | String(20) | no | primary key |
| title | String(200) | no |  |
| citation | String(300) | no |  |
| jurisdiction | String(200) | no |  |
| primary | Boolean | no |  |

## `bvms_order_type` - OrderType

| Column | Type | Null | Description |
|---|---|---|---|
| code | String(40) | no | primary key |
| title_en | String(250) | no |  |
| title_hi | String(250) | no |  |
| statute | String(20) | no |  |
| section | String(30) | no |  |
| kind | String(12) | no |  |
| min_days | Integer | no |  |
| default_days | Integer | no |  |
| template | String(80) | no |  |
| appeal_days | Integer | yes |  |
| appeal_to | String(200) | no |  |
| body_override_en | Text | no |  |
| body_override_hi | Text | no |  |
| active | Boolean | no |  |

## `bvms_otp` - OTPRequest

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| mobile | String(15) | no |  |
| code_hash | String(64) | no |  |
| expires_at | DateTime(tz) | no |  |
| consumed | Boolean | no |  |
| attempts | Integer | no |  |
| created_at | DateTime(tz) | no |  |

## `bvms_sequence` - Sequence

| Column | Type | Null | Description |
|---|---|---|---|
| key | String(60) | no | primary key |
| value | Integer | no |  |

## `bvms_sla_config` - SLAConfig

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| stage | String(40) | no | unique |
| label | String(120) | no |  |
| hours | Integer | no |  |
| escalate_to_role | String(24) | no |  |
| active | Boolean | no |  |

## `bvms_violation_type` - ViolationType

| Column | Type | Null | Description |
|---|---|---|---|
| code | String(10) | no | primary key |
| category | String(40) | no |  |
| title_en | String(250) | no |  |
| title_hi | String(250) | no |  |
| description | Text | no |  |
| contravention_of | Text | no |  |
| legal_basis | JSON | no |  |
| action_path | String(30) | no |  |
| orders_available | JSON | no |  |
| scn_response_days_default | Integer | no |  |
| order_compliance_days_default | Integer | no |  |
| statutory_minimum_days | Integer | no |  |
| severity | String(10) | no |  |
| compoundable | String(12) | no |  |
| evidence_checklist | JSON | no |  |
| schedule_fine_inr | Integer | yes |  |
| schedule_daily_fine_inr | Integer | yes |  |
| appeal | Text | no |  |
| notes | Text | no |  |
| active | Boolean | no |  |
| sort_order | Integer | no |  |

## `bvms_zone` - Zone

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| code | String(10) | no | unique |
| name_en | String(80) | no |  |
| name_hi | String(80) | no |  |
| active | Boolean | no |  |

## `users` - User

| Column | Type | Null | Description |
|---|---|---|---|
| id | Uuid | no | UUID; JWT `sub`. Inside the platform: the unified user registry |
| username | String(150) | no | unique |
| first_name | String(150) | no |  |
| last_name | String(150) | no |  |
| email | String(254) | no |  |
| is_staff | Boolean | no |  |
| is_superuser | Boolean | no |  |
| is_active | Boolean | no |  |
| last_login | DateTime(tz) | yes |  |
| date_joined | DateTime(tz) | no |  |

## `bvms_admin_audit_log` - AdminAuditLog

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigInteger | no | primary key |
| at | DateTime(tz) | no |  |
| actor_id | FK → users | yes |  |
| action | String(40) | no |  |
| target_type | String(40) | no |  |
| target_id | String(60) | no |  |
| before | JSON | no |  |
| after | JSON | no |  |
| order_reference | String(120) | no |  |
| remarks | Text | no |  |
| ip_address | String(45) | yes |  |

## `bvms_app_attest_key` - AppAttestKey

| Column | Type | Null | Description |
|---|---|---|---|
| key_id | String(64) | no | primary key |
| user_id | FK → users | no |  |
| public_key_pem | Text | no |  |
| counter | BigInteger | no |  |
| environment | String(12) | no |  |
| created_at | DateTime(tz) | no |  |
| last_used_at | DateTime(tz) | yes |  |

## `bvms_division` - Division

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| code | String(10) | no | unique |
| zone_id | FK → bvms_zone | no |  |
| name_en | String(80) | no |  |
| active | Boolean | no |  |

## `bvms_inspection_batch` - InspectionBatch

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| title | String(200) | no |  |
| category | String(40) | no |  |
| created_by_id | FK → users | no |  |
| source_file | String(300) | no |  |
| instructions | Text | no |  |
| due_at | DateTime(tz) | yes |  |
| total | Integer | no |  |
| errors | JSON | no |  |

## `bvms_integrity_nonce` - IntegrityNonce

| Column | Type | Null | Description |
|---|---|---|---|
| nonce | String(64) | no | primary key |
| user_id | FK → users | no |  |
| created_at | DateTime(tz) | no |  |
| used_at | DateTime(tz) | yes |  |

## `bvms_land_layer_upload` - LandLayerUpload

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| name | String(200) | no |  |
| layer_key | String(80) | no |  |
| version | Integer | no |  |
| replaces_id | FK → bvms_land_layer_upload | yes |  |
| agency | String(20) | no |  |
| source_file | String(300) | no |  |
| file_format | String(10) | no |  |
| source | String(200) | no |  |
| survey_date | Date | yes |  |
| feature_count | Integer | no |  |
| skipped_count | Integer | no |  |
| uploaded_by_id | FK → users | yes |  |
| remarks | Text | no |  |
| active | Boolean | no |  |
| import_log | Text | no |  |

## `bvms_legacy_batch` - LegacyOrderBatch

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigInteger | no | primary key |
| title | String(200) | no |  |
| source_file | String(300) | no |  |
| created_by_id | FK → users | yes |  |
| created_at | DateTime(tz) | no |  |
| total_rows | Integer | no |  |
| imported | Integer | no |  |
| errors | JSON | no |  |

## `bvms_legal_section` - LegalSection

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| statute_id | FK → bvms_legal_statute | no |  |
| section | String(30) | no |  |
| heading | String(300) | no |  |
| kind | String(20) | no |  |
| text | Text | no |  |
| schedule_fine_inr | Integer | yes |  |
| schedule_daily_fine_inr | Integer | yes |  |
| verify | Boolean | no |  |
| notes | Text | no |  |

## `bvms_officer_profile` - OfficerProfile

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| user_id | FK → users | no | one profile per platform user |
| role | String(24) | no |  |
| designation | String(120) | no |  |
| employee_code | String(40) | no |  |
| mobile | String(15) | no |  |
| email | String(254) | no |  |
| reports_to_id | FK → bvms_officer_profile | yes |  |
| delegation_order_no | String(120) | no |  |
| delegation_order_date | Date | yes |  |
| signature_image | String(300) | no |  |
| parent_profile_id | FK → bvms_officer_profile | yes |  |
| branch_id | FK → bvms_branch | yes |  |
| active | Boolean | no |  |

## `bvms_role_permission` - RolePermission

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| role | String(24) | no |  |
| permission | String(40) | no |  |
| allowed | Boolean | no |  |
| updated_by_id | FK → users | yes |  |
| updated_at | DateTime(tz) | no |  |

## `bvms_workflow_rule` - WorkflowRule

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| status | String(30) | no |  |
| role | String(24) | no |  |
| action | String(40) | no |  |
| allowed | Boolean | no |  |
| updated_by_id | FK → users | yes |  |
| updated_at | DateTime(tz) | no |  |

## `bvms_workflow_setting` - WorkflowSetting

| Column | Type | Null | Description |
|---|---|---|---|
| key | String(60) | no | primary key |
| value | JSON | no | typed by value_type (bool | int | str) |
| value_type | String(10) | no |  |
| label | String(160) | no |  |
| description | Text | no |  |
| group | String(40) | no |  |
| choices | JSON | no |  |
| updated_by_id | FK → users | yes |  |
| updated_at | DateTime(tz) | no |  |

## `bvms_officer_permission_override` - OfficerPermissionOverride

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| profile_id | FK → bvms_officer_profile | no |  |
| permission | String(40) | no |  |
| allowed | Boolean | no |  |
| reason | String(300) | no |  |
| order_reference | String(120) | no |  |
| updated_by_id | FK → users | yes |  |
| updated_at | DateTime(tz) | no |  |

## `bvms_officer_profile_divisions` - association table

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| officerprofile_id | FK → bvms_officer_profile | no |  |
| division_id | FK → bvms_division | no |  |

## `bvms_officer_profile_zones` - association table

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| officerprofile_id | FK → bvms_officer_profile | no |  |
| zone_id | FK → bvms_zone | no |  |

## `bvms_ward` - Ward

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| number | Integer | no | unique |
| name_en | String(120) | no |  |
| name_hi | String(120) | no |  |
| zone_id | FK → bvms_zone | no |  |
| division_id | FK → bvms_division | yes |  |
| boundary | JSON | yes | GeoJSON Polygon/MultiPolygon (WGS84) |
| active | Boolean | no |  |

## `bvms_govt_land_parcel` - GovtLandParcel

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| name | String(200) | no |  |
| agency | String(20) | no |  |
| land_use | String(120) | no |  |
| village | String(120) | no |  |
| khasra_no | String(120) | no |  |
| area_sqm | Numeric(14,2) | yes |  |
| ward_id | FK → bvms_ward | yes |  |
| geometry | JSON | no | GeoJSON Polygon/MultiPolygon (WGS84); bbox cached for fast filtering |
| bbox | JSON | no |  |
| properties | JSON | no |  |
| layer_upload_id | FK → bvms_land_layer_upload | yes |  |
| layer_key | String(80) | no |  |
| active | Boolean | no |  |

## `bvms_inspection_task` - InspectionTask

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| batch_id | FK → bvms_inspection_batch | yes |  |
| category | String(24) | no |  |
| pid | String(40) | no |  |
| pid_snapshot | JSON | no |  |
| address | Text | no |  |
| owner_name | String(200) | no |  |
| owner_mobile | String(15) | no |  |
| latitude | Numeric(10,7) | yes |  |
| longitude | Numeric(10,7) | yes |  |
| ward_id | FK → bvms_ward | yes |  |
| zone_id | FK → bvms_zone | yes |  |
| instructions | Text | no |  |
| priority | String(10) | no |  |
| created_by_id | FK → users | no |  |
| assigned_to_id | FK → users | yes |  |
| assigned_at | DateTime(tz) | yes |  |
| due_at | DateTime(tz) | yes |  |
| status | String(20) | no |  |
| related_case_id | FK → bvms_case | yes |  |
| started_at | DateTime(tz) | yes |  |
| start_latitude | Numeric(10,7) | yes |  |
| start_longitude | Numeric(10,7) | yes |  |
| start_distance_m | Numeric(10,2) | yes |  |
| completed_at | DateTime(tz) | yes |  |
| outcome_remarks | Text | no |  |
| geofence_m | Integer | no |  |

## `bvms_officer_profile_wards` - association table

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| officerprofile_id | FK → bvms_officer_profile | no |  |
| ward_id | FK → bvms_ward | no |  |

## `bvms_sanctioned_plan` - SanctionedPlan

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| plan_no | String(80) | no | unique |
| pid | String(40) | no |  |
| address | Text | no |  |
| ward_id | FK → bvms_ward | yes |  |
| zone_id | FK → bvms_zone | yes |  |
| latitude | Numeric(10,7) | yes |  |
| longitude | Numeric(10,7) | yes |  |
| owner_name | String(200) | no |  |
| owner_mobile | String(15) | no |  |
| plot_area_sqm | Numeric(12,2) | yes |  |
| land_use | String(60) | no |  |
| building_type | String(80) | no |  |
| sanctioned_on | Date | no |  |
| valid_till | Date | yes |  |
| sanction_mode | String(40) | no |  |
| permitted_floors | String(40) | no |  |
| permitted_ground_coverage_pct | Numeric(5,2) | yes |  |
| permitted_far | Numeric(5,2) | yes |  |
| permitted_height_m | Numeric(6,2) | yes |  |
| setbacks | JSON | no |  |
| licence_no | String(80) | no |  |
| licence_holder | String(200) | no |  |
| licence_date | Date | yes |  |
| licence_valid_till | Date | yes |  |
| licence_authority | String(120) | no |  |
| colony_name | String(160) | no |  |
| architect_name | String(160) | no |  |
| architect_registration_no | String(80) | no |  |
| dpc_certificate_on | Date | yes |  |
| occupation_certificate_no | String(80) | no |  |
| occupation_certificate_on | Date | yes |  |
| status | String(20) | no |  |
| source | String(20) | no |  |
| external_ref | String(120) | no |  |
| remarks | Text | no |  |
| created_by_id | FK → users | yes |  |

## `bvms_case` - ViolationCase

| Column | Type | Null | Description |
|---|---|---|---|
| id | Uuid | no | UUID primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| case_no | String(40) | no | unique |
| status | String(30) | no |  |
| status_changed_at | DateTime(tz) | no |  |
| source | String(20) | no | FIELD_INSPECTION | COMPLAINT | DRONE | LEGACY_ORDER ... |
| legacy_reference | String(120) | no |  |
| legacy_batch_id | FK → bvms_legacy_batch | yes |  |
| complaint_ref | String(80) | no |  |
| priority | String(10) | no |  |
| pid | String(40) | no |  |
| pid_snapshot | JSON | no |  |
| pid_linked_mobile | String(15) | no |  |
| alternate_mobile | String(15) | no |  |
| address_line | Text | no |  |
| locality | String(160) | no |  |
| sector | String(60) | no |  |
| village_colony | String(160) | no |  |
| pincode | String(6) | no |  |
| ward_id | FK → bvms_ward | yes |  |
| zone_id | FK → bvms_zone | yes |  |
| division_id | FK → bvms_division | yes |  |
| latitude | Numeric(10,7) | yes |  |
| longitude | Numeric(10,7) | yes |  |
| location_accuracy_m | Numeric(8,2) | yes |  |
| land_type | String(12) | no |  |
| govt_parcel_id | FK → bvms_govt_land_parcel | yes |  |
| sanctioned_plan_id | FK → bvms_sanctioned_plan | yes |  |
| owner_name | String(200) | no |  |
| owner_father_name | String(200) | no |  |
| occupier_name | String(200) | no |  |
| builder_name | String(200) | no |  |
| person_on_site | String(200) | no |  |
| construction_stage | String(20) | no |  |
| plot_area_sqm | Numeric(12,2) | yes |  |
| covered_area_sqm | Numeric(12,2) | yes |  |
| storeys | String(40) | no |  |
| height_m | Numeric(6,2) | yes |  |
| use_observed | String(80) | no |  |
| description | Text | no |  |
| measurements | JSON | no |  |
| reported_by_id | FK → users | no |  |
| assigned_ae_id | FK → users | yes |  |
| assigned_jc_id | FK → users | yes |  |
| current_owner_role | String(24) | no |  |
| stage_due_at | DateTime(tz) | yes |  |
| sla_breached | Boolean | no |  |
| inspected_at | DateTime(tz) | no |  |
| submitted_at | DateTime(tz) | yes |  |
| ae_forwarded_at | DateTime(tz) | yes |  |
| jc_received_at | DateTime(tz) | yes |  |
| scn_issued_at | DateTime(tz) | yes |  |
| scn_served_at | DateTime(tz) | yes |  |
| response_due_at | DateTime(tz) | yes |  |
| response_received_at | DateTime(tz) | yes |  |
| hearing_at | DateTime(tz) | yes |  |
| decided_at | DateTime(tz) | yes |  |
| order_issued_at | DateTime(tz) | yes |  |
| order_served_at | DateTime(tz) | yes |  |
| compliance_due_at | DateTime(tz) | yes |  |
| executed_at | DateTime(tz) | yes |  |
| closed_at | DateTime(tz) | yes |  |
| task_id | FK → bvms_inspection_task | yes | unique |
| inspector_latitude | Numeric(10,7) | yes |  |
| inspector_longitude | Numeric(10,7) | yes |  |
| inspector_distance_m | Numeric(10,2) | yes |  |
| litigation_status | String(20) | no |  |
| litigation_authority | String(30) | no |  |
| stay_until | Date | yes |  |
| next_hearing_on | Date | yes |  |
| stop_work_issued | Boolean | no |  |
| sealed | Boolean | no |  |
| decision | String(30) | no |  |
| decision_reasons | Text | no |  |
| final_order_id | FK → bvms_notice | yes |  |
| closure_reason | Text | no |  |
| demolition_cost_inr | Numeric(12,2) | yes |  |
| cost_recovery_status | String(20) | no |  |

## `bvms_branch_referral` - BranchReferral

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| case_id | FK → bvms_case | no |  |
| branch_id | FK → bvms_branch | no |  |
| referred_by_id | FK → users | no |  |
| referred_at | DateTime(tz) | no |  |
| query | Text | no |  |
| due_at | DateTime(tz) | yes |  |
| hold_case | Boolean | no |  |
| status | String(12) | no |  |
| assigned_to_id | FK → users | yes |  |
| response | Text | no |  |
| recommendation | String(40) | no |  |
| responded_by_id | FK → users | yes |  |
| responded_at | DateTime(tz) | yes |  |
| closed_by_id | FK → users | yes |  |
| closed_at | DateTime(tz) | yes |  |
| closing_remarks | Text | no |  |

## `bvms_case_event` - CaseEvent

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigInteger | no | primary key |
| case_id | FK → bvms_case | no |  |
| at | DateTime(tz) | no |  |
| actor_id | FK → users | yes |  |
| actor_role | String(24) | no |  |
| action | String(40) | no |  |
| from_status | String(30) | no |  |
| to_status | String(30) | no |  |
| remarks | Text | no |  |
| payload | JSON | no |  |
| ip_address | String(45) | yes |  |
| device_id | String(120) | no |  |
| latitude | Numeric(10,7) | yes |  |
| longitude | Numeric(10,7) | yes |  |
| prev_hash | String(64) | no |  |
| hash | String(64) | no | SHA-256 over the event + prev_hash (tamper-evident chain) |

## `bvms_case_violation` - CaseViolation

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| case_id | FK → bvms_case | no |  |
| violation_type_id | FK → bvms_violation_type | no |  |
| details | JSON | no |  |
| remarks | Text | no |  |
| is_primary | Boolean | no |  |

## `bvms_location_integrity` - LocationIntegrityCheck

| Column | Type | Null | Description |
|---|---|---|---|
| id | BigInteger | no | primary key |
| at | DateTime(tz) | no |  |
| officer_id | FK → users | yes |  |
| context | String(14) | no |  |
| decision | String(10) | no | PASS | FLAGGED | REJECTED |
| reasons | JSON | no |  |
| flags | JSON | no |  |
| case_id | FK → bvms_case | yes |  |
| task_id | FK → bvms_inspection_task | yes |  |
| media_id | FK → bvms_media | yes |  |
| latitude | Numeric(10,7) | yes |  |
| longitude | Numeric(10,7) | yes |  |
| accuracy_m | Numeric(10,3) | yes |  |
| altitude_m | Numeric(10,3) | yes |  |
| speed_mps | Numeric(10,3) | yes |  |
| heading | Numeric(10,3) | yes |  |
| provider | String(30) | no |  |
| fix_at | DateTime(tz) | yes |  |
| fix_age_s | Numeric(10,3) | yes |  |
| jitter_m | Numeric(10,3) | yes |  |
| device_id | String(120) | no |  |
| platform | String(10) | no |  |
| source | String(10) | no |  |
| app_version | String(40) | no |  |
| build_number | String(40) | no |  |
| os_version | String(40) | no |  |
| device_model | String(80) | no |  |
| native_module | Boolean | no |  |
| is_physical_device | Boolean | yes |  |
| mock_location | Boolean | yes |  |
| rooted | Boolean | yes |  |
| developer_options | Boolean | yes |  |
| vpn_active | Boolean | yes |  |
| proxy_configured | Boolean | yes |  |
| simulated_by_software | Boolean | yes |  |
| produced_by_accessory | Boolean | yes |  |
| attestation_type | String(20) | no |  |
| attestation_status | String(12) | no |  |
| attestation_detail | JSON | no |  |
| client_ip | String(45) | yes |  |
| ip_intel | JSON | no |  |
| ip_distance_km | Numeric(8,1) | yes |  |
| previous_id | FK → bvms_location_integrity | yes |  |
| travel_distance_km | Numeric(10,2) | yes |  |
| travel_speed_kmph | Numeric(10,1) | yes |  |
| signals | JSON | no |  |

## `bvms_notice` - Notice

| Column | Type | Null | Description |
|---|---|---|---|
| id | Uuid | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| case_id | FK → bvms_case | no |  |
| order_type_id | FK → bvms_order_type | no |  |
| notice_no | String(60) | no | unique |
| kind | String(12) | no |  |
| issued_by_id | FK → users | no |  |
| issued_at | DateTime(tz) | no |  |
| addressee_name | String(200) | no |  |
| addressee_address | Text | no |  |
| addressee_mobiles | JSON | no |  |
| response_days | Integer | no |  |
| response_due_at | DateTime(tz) | yes |  |
| compliance_days | Integer | no |  |
| compliance_due_at | DateTime(tz) | yes |  |
| hearing_at | DateTime(tz) | yes |  |
| hearing_venue | String(200) | no |  |
| operative_text_en | Text | no |  |
| operative_text_hi | Text | no |  |
| html_snapshot | Text | no |  |
| context_snapshot | JSON | no |  |
| pdf | String(300) | no |  |
| signed_pdf | String(300) | no |  |
| document_hash | String(64) | no |  |
| verification_code | String(24) | no | 12-character code printed under the QR; public verify endpoint |
| qr_payload | Text | no |  |
| signature_status | String(10) | no |  |
| signer_name | String(200) | no |  |
| signer_cert_subject | String(300) | no |  |
| signer_cert_serial | String(120) | no |  |
| signed_at | DateTime(tz) | yes |  |
| signature_error | Text | no |  |
| served_at | DateTime(tz) | yes |  |
| served_mode | String(16) | no |  |
| served_by_id | FK → users | yes |  |
| service_remarks | Text | no |  |
| superseded_by_id | FK → bvms_notice | yes |  |
| is_final_order | Boolean | no |  |
| is_legacy | Boolean | no | order issued on paper before the system (not re-signed) |

## `bvms_notification` - Notification

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| user_id | FK → users | no |  |
| case_id | FK → bvms_case | yes |  |
| title | String(200) | no |  |
| body | Text | no |  |
| level | String(10) | no |  |
| read_at | DateTime(tz) | yes |  |

## `bvms_case_response` - CaseResponse

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| case_id | FK → bvms_case | no |  |
| notice_id | FK → bvms_notice | yes |  |
| received_on | Date | no |  |
| received_via | String(10) | no |  |
| submitted_by_name | String(200) | no |  |
| summary | Text | no |  |
| requests_hearing | Boolean | no |  |
| is_within_time | Boolean | no |  |
| uploaded_by_id | FK → users | no |  |
| ae_comments | Text | no |  |
| ae_commented_at | DateTime(tz) | yes |  |
| jc_remarks | Text | no |  |

## `bvms_execution` - ExecutionRecord

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| case_id | FK → bvms_case | no |  |
| order_id | FK → bvms_notice | yes |  |
| action | String(20) | no |  |
| mode | String(12) | no |  |
| executed_on | DateTime(tz) | no |  |
| squad_incharge | String(200) | no |  |
| police_assistance | Boolean | no |  |
| police_station | String(120) | no |  |
| duty_magistrate | String(200) | no |  |
| machinery_used | String(300) | no |  |
| area_demolished_sqm | Numeric(12,2) | yes |  |
| seal_memo_no | String(60) | no |  |
| cost_incurred_inr | Numeric(12,2) | yes |  |
| remarks | Text | no |  |
| recorded_by_id | FK → users | no |  |
| verified_by_id | FK → users | yes |  |
| verified_at | DateTime(tz) | yes |  |

## `bvms_hearing` - Hearing

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| case_id | FK → bvms_case | no |  |
| notice_id | FK → bvms_notice | yes |  |
| scheduled_at | DateTime(tz) | no |  |
| venue | String(200) | no |  |
| presiding_id | FK → users | no |  |
| held_at | DateTime(tz) | yes |  |
| attendees | Text | no |  |
| proceedings | Text | no |  |
| outcome | String(30) | no |  |
| next_date | DateTime(tz) | yes |  |

## `bvms_media` - MediaAttachment

| Column | Type | Null | Description |
|---|---|---|---|
| id | Uuid | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| case_id | FK → bvms_case | yes |  |
| task_id | FK → bvms_inspection_task | yes |  |
| notice_id | FK → bvms_notice | yes |  |
| sanctioned_plan_id | FK → bvms_sanctioned_plan | yes |  |
| kind | String(20) | no |  |
| media_type | String(10) | no |  |
| file | String(300) | no | S3 object key or path under UPLOADS_DIR |
| original_name | String(255) | no |  |
| size_bytes | BigInteger | no |  |
| sha256 | String(64) | no |  |
| latitude | Numeric(10,7) | yes |  |
| longitude | Numeric(10,7) | yes |  |
| accuracy_m | Numeric(8,2) | yes |  |
| altitude_m | Numeric(8,2) | yes |  |
| captured_at | DateTime(tz) | yes |  |
| device_id | String(120) | no |  |
| distance_from_case_m | Numeric(10,2) | yes |  |
| geotag_verified | Boolean | no |  |
| integrity_status | String(12) | no | PASS | FLAGGED | REJECTED | UNVERIFIED (services/location_integrity.py) |
| integrity_check_id | FK → bvms_location_integrity | yes |  |
| caption | String(300) | no |  |
| uploaded_by_id | FK → users | yes |  |

## `bvms_notice_dispatch` - NoticeDispatch

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| notice_id | FK → bvms_notice | no |  |
| channel | String(10) | no |  |
| to | String(120) | no |  |
| message | Text | no |  |
| status | String(12) | no |  |
| provider_ref | String(120) | no |  |
| attempts | Integer | no |  |
| last_error | Text | no |  |
| sent_at | DateTime(tz) | yes |  |

## `bvms_appeal` - Appeal

| Column | Type | Null | Description |
|---|---|---|---|
| id | Integer | no | primary key |
| created_at | DateTime(tz) | no |  |
| updated_at | DateTime(tz) | no |  |
| case_id | FK → bvms_case | no |  |
| order_id | FK → bvms_notice | yes |  |
| authority | String(30) | no |  |
| authority_other | String(200) | no |  |
| filed_on | Date | no |  |
| appeal_no | String(120) | no |  |
| appellant_name | String(200) | no |  |
| counsel_for_mcg | String(200) | no |  |
| status | String(16) | no |  |
| stay_granted | Boolean | no |  |
| stay_order_date | Date | yes |  |
| stay_until | Date | yes |  |
| stay_scope | String(20) | no |  |
| stay_order_id | FK → bvms_media | yes |  |
| conditions | Text | no |  |
| next_hearing_on | Date | yes |  |
| decided_on | Date | yes |  |
| decision_summary | Text | no |  |
| final_order_id | FK → bvms_media | yes |  |
| recorded_by_id | FK → users | no |  |
