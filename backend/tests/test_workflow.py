"""End-to-end workflow tests: JE -> AE -> JC SCN -> service -> response -> order -> service -> execution -> close,
plus statutory-minimum and geotag guards and the hash-chained audit trail."""
from datetime import date, timedelta

import pytest

from app.core.timeutil import now
from app.models import building_violations as m
from app.services.building_violations import workflow as wf
from app.services.building_violations.audit import verify_chain
from tests.helpers import BASE, PNG, add_media, attr, hdr, officer, refresh, run, ward

pytestmark = pytest.mark.anyio


def _case(s, je, w, **over):
    data = dict(pid="GGN012345", pid_linked_mobile="9811100001", address_line="H.No. 123, Sector 14", latitude=28.4700, longitude=77.0450, owner_name="Ramesh Kumar",
                description="Fourth floor over S+3", ward=w)
    data.update(over)
    case = wf.create_case(s, je, data, [{"code": "DV-03"}, {"code": "DV-04"}])
    add_media(s, case, 28.4700, 77.0450, je)
    return case


async def test_full_private_land_flow(db):
    je, ae, jc, clerk, field = [await officer(db, r) for r in ("JE", "AE", "JC", "JC_CLERK", "FIELD_STAFF")]
    case = await run(db, _case, je, await ward(db, 19))
    assert case.land_type == "PRIVATE"  # outside the demo green-belt polygon
    assert case.sanctioned_plan is not None, "plan auto-linked by PID"
    await run(db, wf.submit_to_ae, case, je)
    assert case.status == m.CaseStatus.PENDING_AE
    with pytest.raises(wf.WorkflowError):
        await run(db, wf.jc_issue_notice, case, jc, order_type_code="SCN_261")  # wrong status
    await run(db, wf.ae_forward, case, ae, remarks="ok", recommendation="SCN")
    assert case.status == m.CaseStatus.PENDING_JC
    scn = await run(db, wf.jc_issue_notice, case, jc, order_type_code="SCN_261", remarks="issue")
    await refresh(db, case)
    assert case.status == m.CaseStatus.SCN_ISSUED
    assert scn.pdf
    assert scn.signature_status == "SIGNED"
    assert len(scn.document_hash) == 64
    assert "9811100001" in scn.addressee_mobiles
    assert len(await attr(db, scn, "dispatches")) == 1
    # delivery proof must be geotagged at the property
    far = await run(db, add_media, case, 28.60, 77.30, field, "NOTICE_DELIVERY")
    with pytest.raises(wf.WorkflowError):
        await run(db, wf.record_service, scn, field, mode="AFFIXATION", media_ids=[far.id])
    near = await run(db, add_media, case, 28.4701, 77.0451, field, "NOTICE_DELIVERY")
    await run(db, lambda s: (s.delete(far), s.flush()))
    await run(db, wf.record_service, scn, field, mode="AFFIXATION", media_ids=[near.id])
    await refresh(db, case)
    assert case.status == m.CaseStatus.SCN_SERVED
    assert case.response_due_at is not None
    # clerk uploads the response -> goes straight to JC
    await run(db, wf.record_response, case, clerk, notice=scn, received_on=date.today(), received_via="JC_CLERK", summary="Owner says plan revision applied")
    await refresh(db, case)
    assert case.status == m.CaseStatus.RESPONSE_PENDING_JC
    h = await run(db, wf.schedule_hearing, case, jc, scheduled_at=now() + timedelta(days=3), venue="JC office")
    await run(db, wf.record_hearing, h, jc, proceedings="Heard; no sanction for 4th floor", outcome="HEARD")
    await refresh(db, case)
    assert case.status == m.CaseStatus.RESPONSE_PENDING_JC
    with pytest.raises(wf.WorkflowError):
        await run(db, wf.jc_issue_notice, case, jc, order_type_code="DEMOLITION_ORDER_261", days=2)  # below statutory minimum of 3 days
    order = await run(db, wf.jc_issue_notice, case, jc, order_type_code="DEMOLITION_ORDER_261", days=15, remarks="Not regularisable: FAR exceeded")
    await refresh(db, case)
    assert case.status == m.CaseStatus.ORDER_ISSUED
    assert order.is_final_order
    assert case.decision == "DEMOLITION"
    m2 = await run(db, add_media, case, 28.4700, 77.0450, je, "ORDER_DELIVERY")
    await run(db, wf.record_service, order, je, mode="IN_PERSON", media_ids=[m2.id])
    await refresh(db, case)
    assert case.status == m.CaseStatus.ORDER_SERVED
    assert (case.compliance_due_at - case.order_served_at).days == 15
    # simulate expiry of the 15-day clock
    case.compliance_due_at = now() - timedelta(hours=1)
    await run(db, lambda s: s.flush())
    await run(db, wf.mark_execution_due, case)
    assert case.status == m.CaseStatus.EXECUTION_DUE
    ex_media = await run(db, add_media, case, 28.4700, 77.0450, field, "EXECUTION")
    await run(db, wf.record_execution, case, field, action="DEMOLITION", mode="CORPORATION", executed_on=now(), media_ids=[ex_media.id], police_assistance=True, cost_incurred_inr=45000)
    await refresh(db, case)
    assert case.status == m.CaseStatus.EXECUTED
    await run(db, wf.verify_and_close, case, jc, remarks="Verified")
    assert case.status == m.CaseStatus.CLOSED
    chain = await run(db, verify_chain, case)
    assert chain["ok"]
    assert chain["events"] > 12


async def test_govt_land_408a_flow(db):
    je, ae, jc = [await officer(db, r) for r in ("JE", "AE", "JC")]
    w = await ward(db, 19)
    case = await run(db, wf.create_case, je, dict(address_line="Shed on green belt", latitude=28.4700, longitude=77.0455, description="tin shed", ward=w, alternate_mobile="9811100003"), [{"code": "GL-01"}])
    assert case.land_type == "GOVT_MCG"
    assert case.govt_parcel is not None
    await run(db, add_media, case, 28.4700, 77.0455, je)
    await run(db, wf.submit_to_ae, case, je)
    await run(db, wf.ae_forward, case, ae)
    with pytest.raises(wf.WorkflowError):
        await run(db, wf.jc_issue_notice, case, jc, order_type_code="SCN_408A", days=3)  # statutory 7 days
    scn = await run(db, wf.jc_issue_notice, case, jc, order_type_code="SCN_408A")
    assert scn.response_days == 7
    assert "9811100003" in scn.addressee_mobiles
    with pytest.raises(wf.WorkflowError):
        await run(db, wf.jc_issue_notice, case, jc, order_type_code="DEMOLITION_ORDER_284")  # not available for GL-01


async def test_stop_work_and_sealing_are_interim(db):
    je, ae, jc = [await officer(db, r) for r in ("JE", "AE", "JC")]
    case = await run(db, _case, je, await ward(db, 19))
    await run(db, wf.submit_to_ae, case, je)
    await run(db, wf.ae_forward, case, ae)
    await run(db, wf.jc_issue_notice, case, jc, order_type_code="STOP_WORK_262")
    await refresh(db, case)
    assert case.stop_work_issued
    assert case.status == m.CaseStatus.PENDING_JC
    await run(db, wf.jc_issue_notice, case, jc, order_type_code="SEALING_263A", is_final_order=False)
    await refresh(db, case)
    assert case.sealed


async def test_api_roundtrip(db, client):
    je, ae, jc, clerk = [await officer(db, r) for r in ("JE", "AE", "JC", "JC_CLERK")]
    r = await client.get(f"{BASE}/masters/violation-types/", headers=hdr(je))
    assert r.status_code == 200
    assert len(r.json()) >= 30
    r = await client.get(f"{BASE}/property/pid/GGN012345/", headers=hdr(je))
    assert r.status_code == 200
    assert r.json()["owner_name"] == "Ramesh Kumar"
    r = await client.get(f"{BASE}/gis/check-point/", params={"lat": 28.47, "lng": 77.0455}, headers=hdr(je))
    assert r.json()["land_type"] == "GOVT_MCG"
    payload = {"pid": "GGN012345", "address_line": "H.No. 123", "latitude": 28.47, "longitude": 77.045, "description": "x", "violations": [{"code": "PL-01"}], "land_type": "PRIVATE"}
    r = await client.post(f"{BASE}/cases/", json=payload, headers=hdr(je))
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(f"{BASE}/cases/{cid}/submit/", json={}, headers=hdr(je))
    assert r.status_code == 400  # no media yet
    up = await client.post(f"{BASE}/media/", data={"case": cid, "kind": "INSPECTION", "latitude": "28.4700", "longitude": "77.0450"}, files={"file": ("a.png", PNG, "image/png")}, headers=hdr(je))
    assert up.status_code == 201, up.text
    assert up.json()["geotag_verified"] is True
    r = await client.post(f"{BASE}/cases/{cid}/submit/", json={}, headers=hdr(je))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PENDING_AE"
    assert (await client.post(f"{BASE}/cases/{cid}/ae_forward/", json={"remarks": "go"}, headers=hdr(ae))).status_code == 200
    r = await client.post(f"{BASE}/cases/{cid}/issue_notice/", json={"order_type": "SCN_261", "days": 7}, headers=hdr(jc))
    assert r.status_code == 201, r.text
    nid = r.json()["notice"]["id"]
    code = r.json()["notice"]["verification_code"]
    pdf = await client.get(f"{BASE}/notices/{nid}/pdf/", headers=hdr(jc))
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    pub = await client.get(f"/building-violations/public/verify/{code}/")
    assert pub.json()["valid"] is True
    r = await client.get(f"{BASE}/dashboards/summary/", headers=hdr(jc))
    assert r.status_code == 200
    assert r.json()["scn_issued"] >= 1
    r = await client.get(f"{BASE}/reports/case-register/", params={"export": "csv"}, headers=hdr(jc))
    assert r.status_code == 200
    r = await client.post(f"{BASE}/cases/{cid}/issue_notice/", json={"order_type": "SCN_261"}, headers=hdr(clerk))
    assert r.status_code == 403  # clerk cannot issue
