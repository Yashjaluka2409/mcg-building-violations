"""Branch referrals, admin-configurable rules / permissions / settings, re-assignment and litigation."""
from datetime import date, timedelta

import pytest

from app.models import building_violations as m
from app.services.building_violations import access
from app.services.building_violations import workflow as wf
from app.services.building_violations.scheduler import stay_expiry_sweep
from tests.helpers import BASE, add_media, attr, events, hdr, officer, refresh, run, ward

pytestmark = pytest.mark.anyio


def _case_at_jc(s, je, ae, w):
    case = wf.create_case(s, je, dict(address_line="Shed on green belt", latitude=28.4700, longitude=77.0455, description="tin shed", ward=w, alternate_mobile="9811100003"), [{"code": "GL-01"}])
    add_media(s, case, 28.4700, 77.0455, je)
    wf.submit_to_ae(s, case, je)
    wf.ae_forward(s, case, ae)
    return case


# ---- referrals -----------------------------------------------------------
async def test_referral_blocks_final_order_until_branch_responds(db, client):
    je, ae, jc = [await officer(db, r) for r in ("JE", "AE", "JC")]
    revenue = await officer(db, branch_id="REVENUE")
    planning = await officer(db, branch_id="PLANNING")
    case = await run(db, _case_at_jc, je, ae, await ward(db, 19))
    rev = await run(db, lambda s: s.get(m.Branch, "REVENUE"))
    ref = await run(db, wf.refer_to_branch, case, jc, branch=rev, query="Confirm ownership from jamabandi", hold_case=True)
    assert ref.status == "PENDING"
    assert case.status == m.CaseStatus.PENDING_JC  # main workflow untouched
    scn = await run(db, wf.jc_issue_notice, case, jc, order_type_code="SCN_408A")  # notices still allowed
    mm = await run(db, add_media, case, 28.4700, 77.0455, je, "NOTICE_DELIVERY")
    await run(db, wf.record_service, scn, je, mode="AFFIXATION", media_ids=[mm.id])
    with pytest.raises(wf.WorkflowError):
        await run(db, wf.jc_issue_notice, case, jc, order_type_code="EVICTION_DEMOLITION_ORDER_408A")  # blocked by hold referral
    # planning officer cannot answer a revenue referral
    with pytest.raises(wf.WorkflowError):
        await run(db, wf.respond_to_referral, ref, planning, response="not mine")
    # branch officer sees the case (history) and answers
    r = await client.get(f"{BASE}/cases/{case.id}/", headers=hdr(revenue))
    assert r.status_code == 200
    assert r.json()["available_actions"] == ["respond_branch"]
    assert len(r.json()["events"]) >= 5  # full history visible
    r = await client.post(f"{BASE}/cases/{case.id}/respond_branch/", json={"referral": ref.id, "response": "Khasra 112/2 vests in MCG as per jamabandi 2023-24", "recommendation": "GOVT_LAND_CONFIRMED"}, headers=hdr(revenue))
    assert r.status_code == 200, r.text
    await refresh(db, ref)
    assert ref.status == "RESPONDED"
    # now the JC can pass the final order
    await refresh(db, case)
    order = await run(db, wf.jc_issue_notice, case, jc, order_type_code="EVICTION_DEMOLITION_ORDER_408A", remarks="Ownership confirmed by Revenue")
    assert order.is_final_order
    # branch officer's list is scoped
    r = await client.get(f"{BASE}/referrals/", headers=hdr(revenue))
    assert r.json()["count"] == 1
    assert (await client.get(f"{BASE}/referrals/", headers=hdr(planning))).json()["count"] == 0
    assert (await client.get(f"{BASE}/cases/{case.id}/", headers=hdr(planning))).status_code == 404  # not referred to planning


# ---- admin: workflow rules ---------------------------------------------
async def test_admin_can_switch_off_an_action(db, client):
    je, admin = await officer(db, "JE"), await officer(db, "ADMIN")
    w = await ward(db, 19)
    case = await run(db, wf.create_case, je, dict(address_line="x", description="y", ward=w), [{"code": "PL-01"}])
    await run(db, add_media, case, 28.4700, 77.0455, je)
    r = await client.put(f"{BASE}/admin/workflow-rules/", json={"rules": [{"status": "DRAFT", "role": "JE", "action": "submit_to_ae", "allowed": False}], "order_reference": "MCG/IT/2026/17"}, headers=hdr(admin))
    assert r.status_code == 200
    assert "submit_to_ae" not in r.json()["matrix"]["DRAFT"].get("JE", [])
    access.invalidate()
    with pytest.raises(wf.WorkflowError):
        await run(db, wf.submit_to_ae, case, je)
    # a JE cannot change rules
    assert (await client.put(f"{BASE}/admin/workflow-rules/", json={"rules": []}, headers=hdr(je))).status_code == 403
    # audit log has the change with the order reference
    log = (await client.get(f"{BASE}/admin/audit-log/", headers=hdr(admin))).json()
    assert any(x["action"] == "RULES_UPDATE" and x["order_reference"] == "MCG/IT/2026/17" for x in log)


async def test_setting_skip_ae_review(db, client):
    je, admin = await officer(db, "JE"), await officer(db, "ADMIN")
    w = await ward(db, 19)
    case = await run(db, wf.create_case, je, dict(address_line="x", description="y", ward=w), [{"code": "PL-01"}])
    await run(db, add_media, case, 28.4700, 77.0455, je)
    r = await client.put(f"{BASE}/admin/settings/", json={"values": {"require_ae_review": False}}, headers=hdr(admin))
    assert r.status_code == 200
    access.invalidate()
    await run(db, wf.submit_to_ae, case, je)
    assert case.status == m.CaseStatus.PENDING_JC
    assert case.assigned_jc is not None


# ---- admin: permissions and overrides ----------------------------------
async def test_permission_override_grants_reports_to_je(db, client):
    je, ae, jc, admin = [await officer(db, r) for r in ("JE", "AE", "JC", "ADMIN")]
    assert (await client.get(f"{BASE}/reports/case-register/", headers=hdr(je))).status_code == 403
    prof_id = je.bvms_profile.id
    r = await client.put(f"{BASE}/officers/{prof_id}/permissions/", json={"overrides": [{"permission": "REPORTS_EXPORT", "allowed": True, "reason": "Zone MIS duty"}], "order_reference": "Endst. 1234"}, headers=hdr(admin))
    assert r.status_code == 200, r.text
    access.invalidate()
    assert (await client.get(f"{BASE}/reports/case-register/", headers=hdr(je))).status_code == 200
    me = (await client.get(f"{BASE}/users/me/", headers=hdr(je))).json()
    assert "REPORTS_EXPORT" in me["permissions"]
    # role-level revoke: JC loses BRANCH_REFER
    r = await client.put(f"{BASE}/admin/permissions/", json={"grants": [{"role": "JC", "permission": "BRANCH_REFER", "allowed": False}]}, headers=hdr(admin))
    assert r.status_code == 200
    access.invalidate()
    case = await run(db, _case_at_jc, je, ae, await ward(db, 19))
    planning = await run(db, lambda s: s.get(m.Branch, "PLANNING"))
    with pytest.raises(wf.WorkflowError):
        await run(db, wf.refer_to_branch, case, jc, branch=planning, query="q")


# ---- admin: jurisdiction & re-assignment --------------------------------
async def test_jurisdiction_change_and_bulk_reassign(db, client):
    je, ae, admin = [await officer(db, r) for r in ("JE", "AE", "ADMIN")]
    w = await ward(db, 19)
    case = await run(db, _case_at_jc, je, ae, w)

    def mk(s):
        u = m.User(username="9000000021", first_name="New", last_name="AE")
        s.add(u)
        s.flush()
        p = m.OfficerProfile(user=u, role=m.Role.AE, mobile="9000000021", designation="AE Zone 3")
        s.add(p)
        s.flush()
        return p
    new_ae = await run(db, mk)
    zone3 = await run(db, lambda s: s.query(m.Zone).filter_by(code="3").one())
    r = await client.patch(f"{BASE}/officers/{new_ae.id}/", json={"zones": [zone3.id], "wards": [w.id], "order_reference": "Transfer order 77"}, headers=hdr(admin))
    assert r.status_code == 200, r.text
    r = await client.post(f"{BASE}/admin/reassign-cases/", json={"ward": w.id, "assigned_ae": str(new_ae.user_id), "order_reference": "Transfer order 77"}, headers=hdr(admin))
    assert r.status_code == 200, r.text
    assert r.json()["reassigned"] >= 1
    await refresh(db, case)
    assert case.assigned_ae_id == new_ae.user_id
    assert "REASSIGNED" in await events(db, case)
    log = (await client.get(f"{BASE}/admin/audit-log/", params={"search": "Transfer order 77"}, headers=hdr(admin))).json()
    assert len(log) >= 2


# ---- litigation ---------------------------------------------------------
async def test_stay_requires_uploaded_order_and_resumes_clock(db, client):
    je, ae, jc = [await officer(db, r) for r in ("JE", "AE", "JC")]
    case = await run(db, _case_at_jc, je, ae, await ward(db, 19))
    scn = await run(db, wf.jc_issue_notice, case, jc, order_type_code="SCN_408A")
    await run(db, wf.record_service, scn, je, mode="IN_PERSON")
    order = await run(db, wf.jc_issue_notice, case, jc, order_type_code="EVICTION_DEMOLITION_ORDER_408A", remarks="reasons")
    await run(db, wf.record_service, order, je, mode="IN_PERSON")
    assert case.status == m.CaseStatus.ORDER_SERVED
    with pytest.raises(wf.WorkflowError):  # no stay order uploaded
        await run(db, wf.record_appeal, case, jc, filed_on=date.today(), authority="HIGH_COURT", appeal_no="CWP 1234/2026", stay_granted=True)
    so = await run(db, add_media, case, 28.4700, 77.0455, jc, "STAY_ORDER")
    ap = await run(db, wf.record_appeal, case, jc, filed_on=date.today(), authority="HIGH_COURT", appeal_no="CWP 1234/2026", stay_granted=True, stay_order_media=so,
                   stay_until=date.today() + timedelta(days=2), stay_scope="STATUS_QUO", next_hearing_on=date.today() + timedelta(days=10))
    await refresh(db, case)
    assert case.status == m.CaseStatus.APPEAL_STAY
    assert case.litigation_status == "STAYED"
    assert case.litigation_authority == "HIGH_COURT"
    assert await attr(db, ap, "stay_order.kind") == "STAY_ORDER"
    assert await run(db, stay_expiry_sweep) >= 1  # reminder because the stay expires within 3 days
    await run(db, wf.update_appeal, ap, jc, status="STAY_VACATED", decided_on=date.today(), decision_summary="Stay vacated on 1st hearing", new_compliance_days=7)
    await refresh(db, case)
    assert case.status == m.CaseStatus.ORDER_SERVED
    assert case.litigation_status == "DECIDED"
    assert case.compliance_due_at is not None
    # API: litigation register
    r = await client.get(f"{BASE}/reports/litigation-register/", headers=hdr(jc))
    assert r.status_code == 200
    assert r.json()["count"] == 1
    assert r.json()["rows"][0][4] == "Punjab & Haryana High Court"
