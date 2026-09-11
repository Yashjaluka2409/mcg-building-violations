"""Configurable review hierarchy: labels follow the admin configuration, extra reviewer stages route in
order, a chain without reviewers goes straight to the authority, and a new role inherits its slot."""
import pytest

from app.models import building_violations as m
from app.services.building_violations import workflow as wf
from tests.helpers import BASE, add_media, hdr, officer, run, ward

pytestmark = pytest.mark.anyio

STAGES3 = [{"slot": "REPORTER", "role": "JE", "label_en": "Junior Engineer"}, {"slot": "REVIEWER", "role": "AE", "label_en": "Assistant Engineer"},
           {"slot": "AUTHORITY", "role": "JC", "label_en": "Joint Commissioner"}]


def _case(s, je, w):
    case = wf.create_case(s, je, dict(pid="GGN012345", address_line="H.No. 9, Sector 14", latitude=28.47, longitude=77.045, owner_name="Owner", description="test", ward=w), [{"code": "DV-03"}])
    add_media(s, case, 28.47, 77.045, je)
    return case


async def _put(client, admin, stages, roles=None):
    r = await client.put(f"{BASE}/admin/hierarchy/", json={"stages": stages, "roles": roles or [], "order_reference": "MCG/Comm/2026/1"}, headers=hdr(admin))
    assert r.status_code == 200, r.text
    return r.json()


async def test_default_config_matches_the_shipped_chain(client, db):
    je = await officer(db, "JE")
    r = await client.get(f"{BASE}/masters/workflow-config/", headers=hdr(je))
    assert r.status_code == 200, r.text
    d = r.json()
    assert [s["role"] for s in d["stages"]] == ["JE", "AE", "JC"]
    assert d["statuses"]["PENDING_AE"]["label_en"] == "Pending with Assistant Engineer"
    assert d["actions"]["submit_to_ae"]["label_en"] == "Submit to Assistant Engineer"
    assert d["summary"] == "Junior Engineer → Assistant Engineer → Joint Commissioner"


async def test_renamed_stages_show_everywhere(client, db):
    admin, je = await officer(db, "ADMIN"), await officer(db, "JE")
    stages = [{"slot": "REPORTER", "role": "JE", "label_en": "Building Inspector"}, {"slot": "REVIEWER", "role": "AE", "label_en": "Supervisor"},
              {"slot": "AUTHORITY", "role": "JC", "label_en": "Joint Commissioner"}]
    roles = [{"code": "JE", "label_en": "Building Inspector", "short_label": "BI", "kind": "CHAIN"}, {"code": "AE", "label_en": "Supervisor", "short_label": "SUP", "kind": "CHAIN"}]
    d = await _put(client, admin, stages, roles)
    assert d["statuses"]["PENDING_AE"]["label_en"] == "Pending with Supervisor"
    assert d["statuses"]["RETURNED_TO_JE"]["label_en"].startswith("Returned to Building Inspector")
    assert d["actions"]["submit_to_ae"]["label_en"] == "Submit to Supervisor"
    me = (await client.get(f"{BASE}/users/me/", headers=hdr(je))).json()
    assert me["role_label"] == "Building Inspector" and me["slot"] == "REPORTER" and me["can_create_case"] is True
    case = await run(db, _case, je, await ward(db, 19))
    await run(db, wf.submit_to_ae, case, je)
    body = (await client.get(f"{BASE}/cases/{case.id}/", headers=hdr(je))).json()
    assert body["status"] == "PENDING_AE" and body["status_display"] == "Pending with Supervisor"
    assert body["current_owner_label"] == "Supervisor"
    assert [p["label_en"] for p in body["people"]] == ["Building Inspector", "Supervisor", "Joint Commissioner"]
    rules = (await client.get(f"{BASE}/admin/workflow-rules/", headers=hdr(admin))).json()
    assert rules["role_labels"]["AE"] == "Supervisor"


async def test_two_reviewer_stages_route_in_order(client, db):
    admin, je, ae, xen = [await officer(db, r) for r in ("ADMIN", "JE", "AE", "XEN")]
    stages = [STAGES3[0], STAGES3[1], {"slot": "REVIEWER", "role": "XEN", "label_en": "Executive Engineer"}, STAGES3[2]]
    d = await _put(client, admin, stages)
    assert d["review_enabled"] and len(d["slots"]["REVIEWER"]) == 2
    case = await run(db, _case, je, await ward(db, 19))
    await run(db, wf.submit_to_ae, case, je)
    assert case.status == m.CaseStatus.PENDING_AE and case.review_stage == 1 and case.current_owner_role == "AE"
    with pytest.raises(wf.WorkflowError):        # the XEN stage comes later
        await run(db, wf.ae_forward, case, xen)
    detail = (await client.get(f"{BASE}/cases/{case.id}/", headers=hdr(xen))).json()
    assert "ae_forward" not in detail["available_actions"]
    detail = (await client.get(f"{BASE}/cases/{case.id}/", headers=hdr(ae))).json()
    assert detail["action_labels"]["ae_forward"] == "Forward to Executive Engineer"
    await run(db, wf.ae_forward, case, ae, remarks="ok")
    assert case.status == m.CaseStatus.PENDING_AE and case.review_stage == 2 and case.current_owner_role == "XEN"
    assert case.assigned_ae_id == xen.id
    with pytest.raises(wf.WorkflowError):        # the AE stage has already acted
        await run(db, wf.ae_forward, case, ae)
    inbox = (await client.get(f"{BASE}/cases/", params={"inbox": "1"}, headers=hdr(xen))).json()
    assert case.case_no in [c["case_no"] for c in inbox["results"]]
    detail = (await client.get(f"{BASE}/cases/{case.id}/", headers=hdr(xen))).json()
    assert detail["status_display"] == "Pending with Executive Engineer"
    assert detail["action_labels"]["ae_forward"] == "Forward to Joint Commissioner"
    await run(db, wf.ae_forward, case, xen, remarks="agree")
    assert case.status == m.CaseStatus.PENDING_JC and case.review_stage == 0 and case.current_owner_role == "JC"


async def test_chain_without_reviewer_goes_straight_to_authority(client, db):
    admin, je = await officer(db, "ADMIN"), await officer(db, "JE")
    await _put(client, admin, [STAGES3[0], STAGES3[2]])
    case = await run(db, _case, je, await ward(db, 19))
    await run(db, wf.submit_to_ae, case, je)
    assert case.status == m.CaseStatus.PENDING_JC and case.assigned_jc_id is not None
    cfg = (await client.get(f"{BASE}/masters/workflow-config/", headers=hdr(je))).json()
    assert cfg["actions"]["submit_to_ae"]["label_en"] == "Submit to Joint Commissioner"


async def test_new_role_inherits_its_slot(client, db):
    admin, je, xen = await officer(db, "ADMIN"), await officer(db, "JE"), await officer(db, "XEN")
    roles = [{"code": "SUPERVISOR", "label_en": "Supervisor", "label_hi": "पर्यवेक्षक", "short_label": "SUP", "kind": "CHAIN"}]
    stages = [STAGES3[0], {"slot": "REVIEWER", "role": "SUPERVISOR", "label_en": "Supervisor", "label_hi": "पर्यवेक्षक"}, STAGES3[2]]
    await _put(client, admin, stages, roles)

    def _move(s):   # the demo XEN takes the new role (keeps zones 2-4)
        p = s.query(m.OfficerProfile).filter(m.OfficerProfile.user_id == xen.id).one()
        p.role = "SUPERVISOR"
        s.flush()
    await run(db, _move)
    case = await run(db, _case, je, await ward(db, 19))
    await run(db, wf.submit_to_ae, case, je)
    assert case.current_owner_role == "SUPERVISOR" and case.assigned_ae_id == xen.id
    detail = (await client.get(f"{BASE}/cases/{case.id}/", headers=hdr(xen))).json()    # inherits the reviewer slot's rules and scoping
    assert "ae_forward" in detail["available_actions"] and "ae_return" in detail["available_actions"]
    assert detail["status_display"] == "Pending with Supervisor" and detail["status_display_hi"] == "पर्यवेक्षक के पास लंबित"
    me = (await client.get(f"{BASE}/users/me/", headers=hdr(xen))).json()
    assert me["role_label"] == "Supervisor" and "NOTICE_RESEND_SMS" in me["permissions"]   # AE default permission inherited
    await run(db, wf.ae_forward, case, xen, remarks="ok")
    assert case.status == m.CaseStatus.PENDING_JC


async def test_invalid_chains_are_rejected(client, db):
    admin, je = await officer(db, "ADMIN"), await officer(db, "JE")
    bad = [[STAGES3[1], STAGES3[2]], [STAGES3[0]], [STAGES3[0], STAGES3[1], {"slot": "REVIEWER", "role": "AE", "label_en": "x"}, STAGES3[2]],
           [STAGES3[0], {"slot": "REVIEWER", "role": "NOPE", "label_en": "x"}, STAGES3[2]]]
    for stages in bad:
        r = await client.put(f"{BASE}/admin/hierarchy/", json={"stages": stages, "order_reference": "x"}, headers=hdr(admin))
        assert r.status_code == 400, (stages, r.text)
    r = await client.put(f"{BASE}/admin/hierarchy/", json={"stages": STAGES3, "order_reference": "x"}, headers=hdr(je))
    assert r.status_code == 403
