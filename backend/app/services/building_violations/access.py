"""
Admin-configurable access control:

* WORKFLOW RULES  - (status, role) -> allowed actions. Defaults in DEFAULT_ACTION_MATRIX; stored in
                    WorkflowRule and editable by the admin. "*" status = any status.
* PERMISSIONS     - module-level rights per role (PERMISSIONS catalogue below) with per-officer
                    overrides. Management roles (ADMIN / COMMISSIONER / ADDL_COMMISSIONER) hold everything.
* SETTINGS        - typed routing switches (DEFAULT_SETTINGS) read by the workflow engine.

All three are cached for 30 s per process; `invalidate()` is called on every admin write.
"""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.models.building_violations import AdminAuditLog, Branch, CaseStatus as S, RolePermission, WorkflowRule, WorkflowSetting
from app.models.building_violations import Role
from app.db.util import client_ip, get_or_create

MANAGEMENT_ROLES = (Role.ADMIN, Role.COMMISSIONER, Role.ADDL_COMMISSIONER)

# ---------------------------------------------------------------------------- workflow rules
ACTIVE = [S.PENDING_JC, S.SCN_ISSUED, S.SCN_SERVED, S.RESPONSE_PENDING_AE, S.RESPONSE_PENDING_JC, S.RESPONSE_RECEIVED, S.NO_RESPONSE, S.HEARING_SCHEDULED, S.ORDER_ISSUED, S.ORDER_SERVED, S.APPEAL_STAY, S.EXECUTION_DUE, S.PENDING_AE, S.RETURNED_TO_JE]
DEFAULT_ACTION_MATRIX: dict[str, dict[str, list[str]]] = {
    "*": {"JE": ["create"], "AE": ["create", "refer_branch"], "FIELD_STAFF": ["create"], "XEN": ["refer_branch"], "JC": ["refer_branch", "reassign"], "BRANCH_OFFICER": ["respond_branch"], "ADMIN": ["reassign"]},
    S.DRAFT: {"JE": ["update", "submit_to_ae", "add_media"], "FIELD_STAFF": ["submit_to_ae", "add_media"], "AE": ["update"]},
    S.RETURNED_TO_JE: {"JE": ["update", "submit_to_ae", "add_media"]},
    S.PENDING_AE: {"AE": ["ae_forward", "ae_return", "add_media"], "XEN": ["ae_forward", "ae_return"]},
    S.PENDING_JC: {"JC": ["issue_notice", "issue_order", "drop", "regularise", "add_media"]},
    S.SCN_ISSUED: {"JE": ["record_service", "add_media"], "FIELD_STAFF": ["record_service", "add_media"], "JC": ["issue_notice", "issue_order", "drop"], "JC_CLERK": ["record_response"]},
    S.SCN_SERVED: {"JE": ["record_response", "add_media"], "JC_CLERK": ["record_response", "schedule_hearing"], "JC": ["record_response", "schedule_hearing", "issue_order", "issue_notice", "drop", "regularise"], "AE": ["record_response"]},
    S.RESPONSE_PENDING_AE: {"AE": ["ae_forward_response"], "XEN": ["ae_forward_response"]},
    S.RESPONSE_PENDING_JC: {"JC": ["issue_order", "issue_notice", "schedule_hearing", "drop", "regularise"], "JC_CLERK": ["schedule_hearing", "record_response"]},
    S.RESPONSE_RECEIVED: {"JC": ["issue_order", "schedule_hearing", "drop", "regularise"]},
    S.NO_RESPONSE: {"JC": ["issue_order", "issue_notice", "schedule_hearing", "drop"], "JC_CLERK": ["record_response", "schedule_hearing"], "JE": ["record_response"]},
    S.HEARING_SCHEDULED: {"JC": ["record_hearing", "issue_order", "drop", "regularise"], "JC_CLERK": ["record_hearing", "record_response"]},
    S.ORDER_ISSUED: {"JE": ["record_service", "add_media"], "FIELD_STAFF": ["record_service", "add_media"], "JC": ["record_appeal", "drop"], "JC_CLERK": ["record_appeal"]},
    S.ORDER_SERVED: {"JE": ["record_execution", "add_media"], "FIELD_STAFF": ["record_execution", "add_media"], "JC": ["record_appeal", "record_execution", "drop"], "JC_CLERK": ["record_appeal"]},
    S.APPEAL_STAY: {"JC": ["decide_appeal"], "JC_CLERK": ["decide_appeal"]},
    S.EXECUTION_DUE: {"JE": ["record_execution", "add_media"], "FIELD_STAFF": ["record_execution", "add_media"], "JC": ["record_appeal", "record_execution", "drop"]},
    S.COMPLIED: {"JC": ["close"], "AE": ["close"]},
    S.EXECUTED: {"JC": ["close"], "AE": ["close"]},
    S.CLOSED: {"JC": ["reopen"]},
    S.DROPPED: {"JC": ["reopen"]},
    S.REGULARISED: {"JC": ["reopen"]},
}
ALL_ACTIONS = ["create", "update", "add_media", "submit_to_ae", "ae_forward", "ae_return", "issue_notice", "issue_order", "record_service", "record_response", "ae_forward_response",
               "schedule_hearing", "record_hearing", "drop", "regularise", "record_appeal", "decide_appeal", "record_execution", "close", "reopen", "refer_branch", "respond_branch", "reassign"]
ACTION_LABELS = {"create": "Create inspection", "update": "Edit draft", "add_media": "Add evidence", "submit_to_ae": "Submit for review", "ae_forward": "Forward to JC", "ae_return": "Return to JE",
                 "issue_notice": "Issue notice / SCN / stop-work / sealing", "issue_order": "Pass final order", "record_service": "Record delivery", "record_response": "Upload reply", "ae_forward_response": "Comment & forward reply",
                 "schedule_hearing": "Fix hearing", "record_hearing": "Record hearing", "drop": "Drop case", "regularise": "Regularise / compound", "record_appeal": "Record appeal / stay", "decide_appeal": "Record appeal decision",
                 "record_execution": "Record demolition / sealing", "close": "Verify & close", "reopen": "Reopen", "refer_branch": "Refer to a branch", "respond_branch": "Respond as branch", "reassign": "Re-assign case"}

# ---------------------------------------------------------------------------- permissions
# code: (label, group, default roles)
PERMISSIONS: dict[str, tuple[str, str, list[str]]] = {
    "CASE_VIEW_ALL": ("View cases of all zones (no jurisdiction filter)", "Cases", ["XEN", "VIEWER", "GIS_LAB"]),
    "CASE_VIEW_BRANCH": ("View cases referred to my branch", "Cases", ["BRANCH_OFFICER"]),
    "CASE_EDIT_ANY": ("Edit any case (not only own drafts)", "Cases", []),
    "CASE_REASSIGN": ("Re-assign cases to another AE / JC", "Cases", ["XEN", "JC"]),
    "NOTICE_RESEND_SMS": ("Re-send notice SMS", "Notices", ["JC", "JC_CLERK", "AE", "JE"]),
    "NOTICE_RESIGN": ("Re-run digital signing", "Notices", ["JC"]),
    "NOTICE_VIEW_ALL": ("View notice register of all zones", "Notices", ["XEN", "VIEWER"]),
    "DASHBOARD_VIEW": ("View dashboards", "MIS", ["JE", "AE", "XEN", "JC", "JC_CLERK", "FIELD_STAFF", "VIEWER", "BRANCH_OFFICER", "GIS_LAB"]),
    "REPORTS_EXPORT": ("Run and export reports", "MIS", ["AE", "XEN", "JC", "JC_CLERK", "VIEWER"]),
    "AUDIT_VIEW": ("View admin audit log", "MIS", []),
    "PLANS_VIEW": ("View sanctioned plans register", "Masters", ["JE", "AE", "XEN", "JC", "JC_CLERK", "FIELD_STAFF", "VIEWER", "BRANCH_OFFICER", "GIS_LAB"]),
    "PLANS_MANAGE": ("Add / edit / bulk-upload sanctioned plans", "Masters", ["JE", "AE", "XEN", "JC", "BRANCH_OFFICER"]),
    "LAND_LAYERS_MANAGE": ("Upload / version government-land layers (GIS lab)", "Masters", ["GIS_LAB"]),
    "LEGACY_ORDERS_MANAGE": ("Record and update orders issued before the system (paper demolition / sealing orders)", "Cases", ["JC", "JC_CLERK", "XEN"]),
    "TASKS_ASSIGN": ("Create and assign planned inspections (push PIDs / map points to the field)", "Inspections", ["JC", "AE", "XEN"]),
    "TASKS_VIEW_ALL": ("View all planned inspections", "Inspections", ["JC", "AE", "XEN", "VIEWER", "GIS_LAB"]),
    "TASKS_EXECUTE": ("Receive and execute planned inspections", "Inspections", ["JE", "FIELD_STAFF"]),
    "MASTERS_MANAGE": ("Edit zones / wards / violation types / order types / SLA", "Masters", []),
    "LEGAL_VIEW": ("View legal catalogue", "Masters", ["JE", "AE", "XEN", "JC", "JC_CLERK", "FIELD_STAFF", "VIEWER", "BRANCH_OFFICER", "GIS_LAB"]),
    "OFFICERS_MANAGE": ("Create / edit officers, jurisdictions and supervisors", "Administration", []),
    "CLERK_MANAGE": ("Create clerk sub-logins for own office", "Administration", ["JC"]),
    "WORKFLOW_CONFIGURE": ("Edit workflow rules and routing settings", "Administration", []),
    "ACCESS_CONFIGURE": ("Edit role permissions and per-officer overrides", "Administration", []),
    "BRANCH_MANAGE": ("Add / edit branches", "Administration", []),
    "BRANCH_REFER": ("Refer a case to a branch", "Referrals", ["AE", "XEN", "JC"]),
    "BRANCH_RESPOND": ("Respond to referrals of my branch", "Referrals", ["BRANCH_OFFICER"]),
    "REFERRALS_VIEW_ALL": ("View all branch referrals", "Referrals", ["XEN", "VIEWER"]),
}

# ---------------------------------------------------------------------------- settings
DEFAULT_SETTINGS = [
    ("require_ae_review", True, "bool", "AE review before JC", "If off, a JE submission goes straight to the Joint Commissioner (no AE stage).", "Routing", []),
    ("route_je_response_via_ae", True, "bool", "JE-uploaded replies go via AE", "If off, replies uploaded by the JE go directly to the JC.", "Routing", []),
    ("auto_assign_ae_by_zone", True, "bool", "Auto-assign AE by zone", "Pick the first active AE of the case zone when the JE submits.", "Routing", []),
    ("auto_assign_jc_by_zone", True, "bool", "Auto-assign JC by zone", "Pick the first active JC of the case zone when the AE forwards.", "Routing", []),
    ("block_final_order_on_pending_referral", True, "bool", "Block final orders while a 'hold' referral is pending", "A referral marked 'hold case' must be answered before a demolition / sealing / eviction order is passed.", "Referrals", []),
    ("referral_default_days", 7, "int", "Default days for a branch to respond", "", "Referrals", []),
    ("require_inspection_media", True, "bool", "Require geotagged evidence before submission", "", "Evidence", []),
    ("require_geotag_for_affixation", True, "bool", "Affixation requires a geotagged photo", "", "Evidence", []),
    ("require_geotag_for_execution", True, "bool", "Execution evidence must be geotagged at the site", "", "Evidence", []),
    ("geotag_tolerance_m", 150, "int", "Geotag tolerance (metres)", "Maximum distance between a delivery / execution photo and the property.", "Evidence", []),
    ("sla_escalation_enabled", True, "bool", "SLA escalation notifications", "", "SLA", []),
    ("inspection_geofence_m", 100, "int", "Geofence for planned inspections (metres)", "A field officer can start a pushed inspection only within this distance of the property point.", "Inspections", []),
    ("require_geofence_for_task_inspection", True, "bool", "Enforce the geofence when recording a case from a task", "The officer's device location must be within the geofence of the task point when the inspection is saved.", "Inspections", []),
    # --- Location integrity (anti-GPS-spoofing); evaluated in services/location_integrity.py -------------------
    ("block_mock_location", True, "bool", "Reject mock / fake GPS", "Reject evidence when the device reports that the location came from a mock provider (FlyGPS, Fake GPS Location and similar) or was simulated by software (computer-tethered spoofing on iOS).", "Location integrity", []),
    ("block_rooted_devices", True, "bool", "Reject rooted / jailbroken devices", "Root and jailbreak tools can hide mock-location flags, so evidence from such devices is refused.", "Location integrity", []),
    ("block_emulators", True, "bool", "Reject emulators / simulators", "The app must run on a physical phone.", "Location integrity", []),
    ("block_developer_options", True, "bool", "Reject Android phones with Developer options on", "Mock-location apps only work while Developer options are enabled, so capture is refused until they are switched off.", "Location integrity", []),
    ("block_vpn_or_proxy", True, "bool", "Reject VPN / proxy", "Reject evidence captured while a VPN or a system proxy is active on the device, or when the request arrives from a known VPN / proxy / Tor IP address (needs an IP-intelligence provider for the IP part).", "Location integrity", []),
    ("block_web_geotags", False, "bool", "Reject geotagged field evidence uploaded from a browser", "Browser locations cannot be verified. Turn on in production so geotagged field evidence is accepted only from the mobile app; browser uploads of documents (replies, orders) are unaffected.", "Location integrity", []),
    ("require_native_integrity_module", False, "bool", "Require the app's native anti-spoofing checks", "Reject evidence from app builds that cannot run the native checks (Expo Go, development builds, web). Turn on once the production app build is distributed to the field.", "Location integrity", []),
    ("require_device_attestation", False, "bool", "Require device attestation (Play Integrity / App Attest)", "Every capture must carry a verdict from Google Play Integrity (Android) or Apple App Attest (iOS) proving a genuine, unmodified app on an untampered device. Needs the server keys described in docs/09-SECURITY-NOTES.md.", "Location integrity", []),
    ("max_location_age_s", 120, "int", "Maximum age of a GPS fix (seconds)", "A fix older than this at the moment of capture is rejected (the app always requests a fresh fix).", "Location integrity", []),
    ("max_location_accuracy_m", 100, "int", "Accuracy radius that is flagged (metres)", "Fixes with a wider accuracy radius are accepted but flagged for supervisory review.", "Location integrity", []),
    ("max_plausible_speed_kmph", 200, "int", "Maximum plausible travel speed (km/h)", "If an officer's consecutive locations (more than 1 km apart) imply faster travel than this, the later capture is rejected as teleporting.", "Location integrity", []),
    ("ip_geo_max_distance_km", 500, "int", "Flag when the IP address geolocates far from the GPS (km)", "Only with an IP-intelligence provider configured. Mobile-network IPs legitimately geolocate to a gateway city, so this only flags; 0 disables.", "Location integrity", []),
    ("auto_assign_tasks_by_ward", True, "bool", "Auto-assign pushed inspections to the JE of the ward", "Falls back to the JE of the zone; otherwise the task waits for manual assignment.", "Inspections", []),
    ("map_history_events", 6, "int", "Events shown in map pop-ups", "", "Map", []),
    ("require_stay_order_upload", True, "bool", "Stay must be backed by an uploaded order", "A stay can be recorded only after the stay / interim order of the Divisional Commissioner or court is uploaded to the case file.", "Litigation", []),
    ("stay_expiry_reminder_days", 3, "int", "Remind before a stay expires (days)", "JC and JE are reminded this many days before `stay_until`, and again when it has passed.", "Litigation", []),
    ("allow_jc_clerk_hearing", True, "bool", "JC clerk may fix and record hearings", "", "Routing", []),
]

_cache: dict = {"rules": None, "perms": None, "settings": None, "at": 0.0}
TTL = 30.0


def invalidate():
    _cache.update({"rules": None, "perms": None, "settings": None, "at": 0.0})


def _fresh():
    if time.time() - _cache["at"] > TTL:
        invalidate()
        _cache["at"] = time.time()


# ---- rules -----------------------------------------------------------------
def rules_matrix(db: Session) -> dict[tuple[str, str], set[str]]:
    _fresh()
    if _cache["rules"] is None:
        m: dict[tuple[str, str], set[str]] = {}
        rows = db.query(WorkflowRule).all()
        if rows:
            for r in rows:
                if r.allowed:
                    m.setdefault((r.status, r.role), set()).add(r.action)
        else:  # not seeded yet -> defaults
            for st, roles in DEFAULT_ACTION_MATRIX.items():
                for role, acts in roles.items():
                    m.setdefault((st, role), set()).update(acts)
        _cache["rules"] = m
    return _cache["rules"]


def is_action_allowed(db: Session, status: str, role: str, action: str) -> bool:
    if role in MANAGEMENT_ROLES:
        return True
    m = rules_matrix(db)
    return action in m.get((status, role), set()) or action in m.get(("*", role), set())


def actions_for(db: Session, status: str, role: str) -> list[str]:
    if role in MANAGEMENT_ROLES:
        acts: set[str] = set()
        for (st, _r), a in rules_matrix(db).items():
            if st in (status, "*"):
                acts.update(a)
        return sorted(acts)
    m = rules_matrix(db)
    return sorted(m.get((status, role), set()) | m.get(("*", role), set()))


def seed_rules(db: Session, force: bool = False) -> int:
    if not force and db.query(WorkflowRule.id).first():
        return 0
    n = 0
    for st, roles in DEFAULT_ACTION_MATRIX.items():
        for role, acts in roles.items():
            for a in acts:
                _, created = get_or_create(db, WorkflowRule, defaults={"allowed": True}, status=st, role=role, action=a)
                n += int(created)
    invalidate()
    return n


# ---- permissions -----------------------------------------------------------
def role_permissions(db: Session) -> dict[str, set[str]]:
    _fresh()
    if _cache["perms"] is None:
        m: dict[str, set[str]] = {}
        rows = db.query(RolePermission).all()
        if rows:
            for r in rows:
                if r.allowed:
                    m.setdefault(r.role, set()).add(r.permission)
        else:
            for code, (_l, _g, roles) in PERMISSIONS.items():
                for role in roles:
                    m.setdefault(role, set()).add(code)
        _cache["perms"] = m
    return _cache["perms"]


def permissions_for(db: Session, user) -> set[str]:
    prof = getattr(user, "bvms_profile", None)
    if not prof or not prof.active:
        return set()
    if prof.role in MANAGEMENT_ROLES:
        return set(PERMISSIONS)
    perms = set(role_permissions(db).get(prof.role, set()))
    for o in prof.permission_overrides:
        if o.allowed:
            perms.add(o.permission)
        else:
            perms.discard(o.permission)
    return perms


def has_perm(db: Session, user, code: str) -> bool:
    return code in permissions_for(db, user)


def seed_permissions(db: Session, force: bool = False) -> int:
    if not force and db.query(RolePermission.id).first():
        return 0
    n = 0
    for code, (_l, _g, roles) in PERMISSIONS.items():
        for role in roles:
            _, created = get_or_create(db, RolePermission, defaults={"allowed": True}, role=role, permission=code)
            n += int(created)
    invalidate()
    return n


# ---- settings --------------------------------------------------------------
def all_settings(db: Session) -> dict:
    _fresh()
    if _cache["settings"] is None:
        d = {k: v for k, v, *_ in DEFAULT_SETTINGS}
        for row in db.query(WorkflowSetting).all():
            d[row.key] = row.value
        _cache["settings"] = d
    return _cache["settings"]


def get_setting(db: Session, key: str, default=None):
    return all_settings(db).get(key, default)


def geotag_tolerance_m(db: Session) -> int:
    try:
        return int(get_setting(db, "geotag_tolerance_m", app_settings.BVMS_GEOTAG_TOLERANCE_M))
    except (TypeError, ValueError):
        return app_settings.BVMS_GEOTAG_TOLERANCE_M


def seed_settings(db: Session) -> int:
    n = 0
    for key, value, vtype, label, desc, group, choices in DEFAULT_SETTINGS:
        _, created = get_or_create(db, WorkflowSetting, defaults={"value": value, "value_type": vtype, "label": label, "description": desc, "group": group, "choices": choices}, key=key)
        n += int(created)
    invalidate()
    return n


def seed_branches(db: Session) -> int:
    defaults = [
        ("PLANNING", "Planning Branch (Town Planning wing)", "योजना शाखा", "District Town Planner (MCG)", "Reports on sanction status, zoning, permissible coverage / FAR, regularisation possibility, controlled-area status."),
        ("REVENUE", "Revenue Branch", "राजस्व शाखा", "Tehsildar / Revenue Officer (MCG)", "Reports on ownership, khasra / jamabandi, whether the land vests in the Corporation / Government, demarcation."),
        ("LEGAL", "Legal Branch", "विधि शाखा", "Law Officer", "Opinion on legal sustainability, court cases, stays, prosecution."),
        ("ENGINEERING", "Engineering Branch", "अभियांत्रिकी शाखा", "Executive Engineer", "Structural safety, drains / road land, execution feasibility."),
        ("FIRE", "Fire Wing", "अग्निशमन शाखा", "Fire Officer", "Fire safety / NOC status for high-rise buildings."),
    ]
    n = 0
    for code, en, hi, head, desc in defaults:
        _, created = get_or_create(db, Branch, defaults={"name_en": en, "name_hi": hi, "head_designation": head, "description": desc}, code=code)
        n += int(created)
    return n


def seed_all(db: Session) -> dict:
    return {"rules": seed_rules(db), "permissions": seed_permissions(db), "settings": seed_settings(db), "branches": seed_branches(db)}


def log_admin(db: Session, actor, action: str, target_type: str = "", target_id="", before=None, after=None, order_reference: str = "", remarks: str = "", request=None):
    from app.db.util import jsonable
    row = AdminAuditLog(actor_id=getattr(actor, "id", None), action=action, target_type=target_type, target_id=str(target_id or ""),
                        before=jsonable(before or {}), after=jsonable(after or {}), order_reference=order_reference or "", remarks=remarks or "", ip_address=client_ip(request))
    db.add(row)
    db.flush()
    return row
