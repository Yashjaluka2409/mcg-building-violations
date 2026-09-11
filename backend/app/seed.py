"""Data loaders (the Django management commands):

* load_legal_catalogue - statutes, sections, violation types, order types from shared/legal/*.json, SLA defaults,
  workflow rules / permissions / settings / branches.
* seed_demo - zones / wards / divisions, demo officers (OTP login), demo government-land parcels, a sanctioned
  plan and (optionally) sample cases and planned inspections.

Demo logins (standalone mode, OTP = BVMS_OTP_DEMO_CODE, default 123456):
  JE      9000000001   AE       9000000002   JC       9000000003
  CLERK   9000000004   XEN      9000000005   ADMIN    9000000009
  FIELD   9000000006   ADDL.COMMR 9000000007
  PLANNING BRANCH 9000000011   REVENUE BRANCH 9000000012   LEGAL BRANCH 9000000013   GIS LAB 9000000014
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutil import now
from app.models import building_violations as m
from app.db.util import get_or_create, update_or_create
from app.services.building_violations import access
from app.services.building_violations.sla import DEFAULT_ESCALATION, DEFAULT_SLA_HOURS

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00"
       b"\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

WARD_ZONES = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 10: 2, 11: 2, 12: 2, 13: 2, 14: 2, 15: 2, 16: 2, 17: 2, 18: 2,
              19: 3, 20: 3, 21: 3, 22: 3, 23: 3, 24: 3, 25: 3, 26: 3, 27: 3, 28: 4, 29: 4, 30: 4, 31: 4, 32: 4, 33: 4, 34: 4, 35: 4, 36: 4}
DEMO_OFFICERS = [
    ("9000000001", m.Role.JE, "Junior Engineer, Zones 2-4", "Amit", "Sharma", [2, 3, 4]),
    ("9000000002", m.Role.AE, "Assistant Engineer, Zones 2-4", "Neha", "Verma", [2, 3, 4]),
    ("9000000003", m.Role.JC, "Joint Commissioner, Zones 2-4", "Vishal", "Kumar", [2, 3, 4]),
    ("9000000004", m.Role.JC_CLERK, "Clerk, Office of JC", "Sunil", "Yadav", [2, 3, 4]),
    ("9000000005", m.Role.XEN, "Executive Engineer", "Rakesh", "Singh", [2, 3, 4]),
    ("9000000006", m.Role.FIELD_STAFF, "Enforcement Inspector", "Deepak", "Rao", [2, 3, 4]),
    ("9000000007", m.Role.ADDL_COMMISSIONER, "Additional Commissioner", "Yash", "Jaluka", None),
    ("9000000009", m.Role.ADMIN, "Module Administrator (IT Cell)", "IT", "Admin", None),
    ("9000000011", m.Role.BRANCH_OFFICER, "District Town Planner (Planning Branch)", "Kavita", "Sharma", None),
    ("9000000012", m.Role.BRANCH_OFFICER, "Tehsildar (Revenue Branch)", "Om", "Prakash", None),
    ("9000000013", m.Role.BRANCH_OFFICER, "Law Officer (Legal Branch)", "Meenakshi", "Rana", None),
    ("9000000014", m.Role.GIS_LAB, "GIS Analyst (GIS Lab)", "Rohit", "Bansal", None),
]
BRANCH_OF = {"9000000011": "PLANNING", "9000000012": "REVENUE", "9000000013": "LEGAL"}


def load_legal_catalogue(db: Session, legal_dir: str | Path | None = None) -> dict:
    d = Path(legal_dir or settings.LEGAL_DIR)
    sections = json.loads((d / "legal_sections.json").read_text(encoding="utf-8"))
    cat = json.loads((d / "violation_catalogue.json").read_text(encoding="utf-8"))
    for st in sections["statutes"]:
        update_or_create(db, m.LegalStatute, defaults={"title": st["title"], "citation": st.get("citation", ""), "jurisdiction": st.get("jurisdiction", ""), "primary": st.get("primary", True)}, code=st["code"])
    n = 0
    for s in sections["sections"]:
        update_or_create(db, m.LegalSection, defaults={
            "heading": s["heading"], "kind": s.get("kind", "substantive"), "text": s["text"],
            "schedule_fine_inr": s.get("schedule_fine_inr"), "schedule_daily_fine_inr": s.get("schedule_daily_fine_inr"),
            "verify": s.get("verify", False), "notes": s.get("notes") or ""}, statute_id=s["statute"], section=s["section"])
        n += 1
    for code, ot in cat["order_types"].items():
        update_or_create(db, m.OrderType, defaults={
            "title_en": ot["title_en"], "title_hi": ot.get("title_hi", ""), "statute": ot["statute"], "section": ot["section"], "kind": ot["kind"],
            "min_days": ot.get("min_days", 0), "default_days": ot.get("default_days", 0), "template": ot["template"],
            "appeal_days": ot.get("appeal_days"), "appeal_to": ot.get("appeal_to") or ""}, code=code)
    for i, v in enumerate(cat["violations"]):
        update_or_create(db, m.ViolationType, defaults={
            "category": v["category"], "title_en": v["title_en"], "title_hi": v.get("title_hi", ""), "description": v.get("description", ""),
            "contravention_of": v.get("contravention_of", ""), "legal_basis": v.get("legal_basis", []), "action_path": v["action_path"],
            "orders_available": v.get("orders_available", []), "scn_response_days_default": v.get("scn_response_days_default", 7),
            "order_compliance_days_default": v.get("order_compliance_days_default", 15), "statutory_minimum_days": v.get("statutory_minimum_days", 0),
            "severity": v.get("severity", "HIGH"), "compoundable": v.get("compoundable", "NO"), "evidence_checklist": v.get("evidence_checklist", []),
            "schedule_fine_inr": v.get("schedule_fine_inr"), "schedule_daily_fine_inr": v.get("schedule_daily_fine_inr"), "appeal": v.get("appeal") or "",
            "notes": v.get("notes") or "", "active": v.get("active", True), "sort_order": i}, code=v["code"])
    for stage, hours in DEFAULT_SLA_HOURS.items():
        get_or_create(db, m.SLAConfig, defaults={"label": stage.replace("_", " ").title(), "hours": hours, "escalate_to_role": DEFAULT_ESCALATION.get(stage, "") or ""}, stage=stage)
    seeded = access.seed_all(db)
    db.flush()
    return {"statutes": db.query(m.LegalStatute).count(), "sections": n, "violation_types": db.query(m.ViolationType).count(), "order_types": db.query(m.OrderType).count(), "access": seeded}


def seed_demo(db: Session, with_cases: bool = False) -> dict:
    load_legal_catalogue(db)
    zones = {}
    for z in range(1, 5):
        zones[z], _ = get_or_create(db, m.Zone, defaults={"name_en": f"Zone {z}", "name_hi": f"ज़ोन {z}"}, code=str(z))
    for z in range(1, 5):
        for s in "AB":
            get_or_create(db, m.Division, defaults={"zone_id": zones[z].id, "name_en": f"Engineering Division {z}{s}"}, code=f"{z}{s}")
    for w, z in WARD_ZONES.items():
        div = db.query(m.Division).filter(m.Division.zone_id == zones[z].id).order_by(m.Division.id).first()
        get_or_create(db, m.Ward, defaults={"zone_id": zones[z].id, "name_en": f"Ward {w}", "name_hi": f"वार्ड {w}", "division_id": div.id if div else None}, number=w)
    jc = None
    for mobile, role, desig, first, last, zone in DEMO_OFFICERS:
        u, _ = get_or_create(db, m.User, defaults={"first_name": first, "last_name": last}, username=mobile)
        if role == m.Role.ADMIN and not u.is_staff:
            u.is_staff = u.is_superuser = True
        p, created = get_or_create(db, m.OfficerProfile, defaults={"role": role, "designation": desig, "mobile": mobile, "email": f"{first.lower()}.{last.lower()}@mcg.gov.in"}, user_id=u.id)
        for z in (zone or []):
            if zones[z] not in p.zones:
                p.zones.append(zones[z])
        if mobile in BRANCH_OF:
            p.branch_id = BRANCH_OF[mobile]
        if role == m.Role.JC:
            jc = p
            p.delegation_order_no = "MCG/Comm/Delegation/2026/114"
            p.delegation_order_date = date(2026, 4, 1)
        db.flush()
    clerk = db.query(m.OfficerProfile).filter(m.OfficerProfile.role == m.Role.JC_CLERK).order_by(m.OfficerProfile.id).first()
    if clerk and jc:
        clerk.parent_profile_id = jc.id
    je = db.query(m.OfficerProfile).filter(m.OfficerProfile.role == m.Role.JE).order_by(m.OfficerProfile.id).first()
    ae = db.query(m.OfficerProfile).filter(m.OfficerProfile.role == m.Role.AE).order_by(m.OfficerProfile.id).first()
    if je and ae:
        je.reports_to_id = ae.id
    db.flush()
    # a couple of government land parcels (demo polygons near Sector 14 / Sushant Lok)
    if not db.query(m.GovtLandParcel.id).first():
        from app.services.building_violations.geo import geojson_bbox
        g1 = {"type": "Polygon", "coordinates": [[[77.0452, 28.4690], [77.0470, 28.4690], [77.0470, 28.4715], [77.0452, 28.4715], [77.0452, 28.4690]]]}
        g2 = {"type": "Polygon", "coordinates": [[[77.0790, 28.4610], [77.0820, 28.4610], [77.0820, 28.4635], [77.0790, 28.4635], [77.0790, 28.4610]]]}
        w19 = db.query(m.Ward).filter(m.Ward.number == 19).one()
        w30 = db.query(m.Ward).filter(m.Ward.number == 30).one()
        db.add(m.GovtLandParcel(name="Green belt, Sector 14 (demo)", agency="MCG", land_use="Green belt", village="Gurugram", khasra_no="112/2", ward_id=w19.id, geometry=g1, bbox=geojson_bbox(g1), properties={}))
        db.add(m.GovtLandParcel(name="Community site, Sushant Lok-1 (demo)", agency="HSVP", land_use="Community facility", village="Sukhrali", khasra_no="45", ward_id=w30.id, geometry=g2, bbox=geojson_bbox(g2), properties={}))
    if not db.query(m.SanctionedPlan.id).first():
        w19 = db.query(m.Ward).filter(m.Ward.number == 19).one()
        db.add(m.SanctionedPlan(plan_no="MCG/BP/2025/00412", pid="GGN012345", address="H.No. 123, Sector 14, Gurugram", ward_id=w19.id, zone_id=zones[2].id,
                                latitude=28.4700, longitude=77.0450, owner_name="Ramesh Kumar", owner_mobile="9811100001", plot_area_sqm=250.84, land_use="Residential",
                                sanctioned_on=date(2025, 6, 12), valid_till=date(2027, 6, 11), sanction_mode="self-certification", permitted_floors="S+3",
                                permitted_ground_coverage_pct=66, permitted_far=2.0, permitted_height_m=15, setbacks={"front": 3, "rear": 3, "side": 0},
                                architect_name="Ar. P. Mehta", architect_registration_no="CA/2010/48211", licence_authority="MCG", source="MANUAL"))
    db.flush()
    out = {"officers": db.query(m.OfficerProfile).count(), "wards": db.query(m.Ward).count()}
    if with_cases:
        out["cases"] = _sample_cases(db)
    return out


def _sample_cases(db: Session) -> list[str]:
    from app.services.building_violations import tasks as ts
    from app.services.building_violations import workflow as wf
    from app.services.building_violations.media import create_attachment
    je = db.query(m.OfficerProfile).filter(m.OfficerProfile.role == m.Role.JE).order_by(m.OfficerProfile.id).first().user
    ae = db.query(m.OfficerProfile).filter(m.OfficerProfile.role == m.Role.AE).order_by(m.OfficerProfile.id).first().user
    jc = db.query(m.OfficerProfile).filter(m.OfficerProfile.role == m.Role.JC).order_by(m.OfficerProfile.id).first().user
    ward = lambda n: db.query(m.Ward).filter(m.Ward.number == n).one()  # noqa: E731
    samples = [
        dict(pid="GGN012345", pid_linked_mobile="9811100001", address_line="H.No. 123, Sector 14", locality="Sector 14", latitude=28.4700, longitude=77.0450, owner_name="Ramesh Kumar",
             storeys="S+4", covered_area_sqm=210, description="Fourth floor being raised over sanctioned S+3; rear setback covered with rooms.", ward=ward(19),
             measurements={"floors_permitted": "S+3", "floors_actual": "S+4", "rear_setback_required_m": 3, "rear_setback_actual_m": 0.6}),
        dict(address_line="Boundary wall and shed inside green belt opposite Sector 14 market", locality="Sector 14", latitude=28.4700, longitude=77.0455, owner_name="Unknown (Sh. Balwan)",
             storeys="G", description="Brick boundary wall (40 m) and tin shed raised on MCG green belt; used as tyre repair shop.", ward=ward(19), alternate_mobile="9811100003"),
        dict(pid="GGN098765", pid_linked_mobile="9811100002", address_line="Plot 45, Sushant Lok Phase-1", locality="Sushant Lok-1", latitude=28.4620, longitude=77.0800, owner_name="Sunita Devi",
             storeys="B+G+4", description="Basement converted to gym; stilt parking enclosed as shops.", ward=ward(30), construction_stage="OCCUPIED"),
    ]
    viols = [[{"code": "DV-03"}, {"code": "DV-04"}], [{"code": "GL-01"}], [{"code": "DV-06"}, {"code": "DV-07"}, {"code": "MU-01"}]]
    made = []
    for data, vv in zip(samples, viols):
        case = wf.create_case(db, je, data, vv)
        mm = create_attachment(db, data=PNG, filename="demo.png", uploaded_by=je, kind="INSPECTION", media_type="IMAGE", case=case, latitude=data["latitude"], longitude=data["longitude"], accuracy_m=6, captured_at=now(), caption="Front view (demo)")
        wf.attach_media(db, case, [mm.id], je)
        made.append(case)
    wf.submit_to_ae(db, made[0], je, remarks="Please forward for SCN")
    wf.ae_forward(db, made[0], ae, remarks="Violations confirmed on site", recommendation="SCN")
    wf.jc_issue_notice(db, made[0], jc, order_type_code="SCN_261", remarks="Issue SCN with stop-work direction")
    wf.submit_to_ae(db, made[1], je)
    wf.ae_forward(db, made[1], ae, remarks="Encroachment on green belt confirmed against GIS layer", recommendation="DEMOLITION")
    wf.refer_to_branch(db, made[1], jc, branch=db.get(m.Branch, "REVENUE"), query="Please confirm from the jamabandi / mussavi whether khasra 112/2 vests in the Corporation and furnish the demarcation report.", hold_case=True)
    wf.refer_to_branch(db, made[0], jc, branch=db.get(m.Branch, "PLANNING"), query="Report on the sanctioned plan MCG/BP/2025/00412: permissible floors / FAR and whether the 4th floor is regularisable under HBC 2017.")
    wf.submit_to_ae(db, made[2], je)
    rows = [{"pid": "GGN012345", "address": "H.No. 123, Sector 14", "latitude": 28.4700, "longitude": 77.0450, "ward_number": 19, "owner_name": "Ramesh Kumar", "owner_mobile": "9811100001", "category": "PG_HOSTEL"},
            {"pid": "GGN098765", "address": "Plot 45, Sushant Lok Phase-1", "latitude": 28.4620, "longitude": 77.0800, "ward_number": 30, "owner_name": "Sunita Devi", "owner_mobile": "9811100002", "category": "PG_HOSTEL"},
            {"pid": "", "address": "Plot 77, Sector 15 Part-II (map point)", "latitude": 28.4665, "longitude": 77.0410, "ward_number": 19, "category": "DRONE_FLAG", "instructions": "Drone change-detection flag: new roof slab visible since June; verify sanction."}]
    ts.bulk_create_from_rows(db, jc, rows, title="PG / hostel verification drive - Zones 3-4 (demo)", category="PG_HOSTEL",
                             instructions="Verify whether the premises are run as a paying-guest accommodation / hostel without change of land use; count rooms, occupants, kitchens; check fire exits and parking. Record a violation or report 'no violation' on site.",
                             due_days=7, default_assignee=je, lookup_pid=False)
    db.flush()
    return [c.case_no for c in made]
