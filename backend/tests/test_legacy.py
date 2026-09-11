"""Orders issued before the system: single import at each stage, bulk register import, historical status updates,
permission, duplicate protection, audit chain, register and dashboard."""
import uuid
from datetime import date

import pytest

from app.models import building_violations as m
from app.services.building_violations.audit import verify_chain
from tests.helpers import BASE, attr, events, get, hdr, officer, run

pytestmark = pytest.mark.anyio


async def _order(db, **kw):
    code = await run(db, lambda s: s.query(m.ViolationType).order_by(m.ViolationType.sort_order, m.ViolationType.code).first().code)
    d = {"order_no": "MCG/JC-2/DEMO/2023/0412", "order_date": "2023-08-14", "order_type": "DEMOLITION_ORDER_261", "issued_by_name": "R. K. Sharma",
         "issued_by_designation": "Joint Commissioner, Zone 2", "pid": "GGN012345", "address_line": "H.No. 123, Sector 14", "ward_number": 19,
         "owner_name": "Ramesh Kumar", "pid_linked_mobile": "9811100001", "compliance_days": 15, "legacy_reference": "Demolition order register 2023-24 p.61",
         "violations": [{"code": code, "remarks": "third floor"}]}
    d.update(kw)
    return d


async def _case(db, cid):
    return await get(db, m.ViolationCase, id=uuid.UUID(str(cid)))


# ---- single imports -------------------------------------------------------------
async def test_import_order_issued_only(db, client):
    jc = await officer(db, "JC")
    r = await client.post(f"{BASE}/legacy-orders/", json=await _order(db), headers=hdr(jc))
    assert r.status_code == 201, r.text
    case = await _case(db, r.json()["id"])
    assert (case.source, case.status, case.decision) == ("LEGACY_ORDER", m.CaseStatus.ORDER_ISSUED, "DEMOLITION")
    n = await attr(db, case, "final_order")
    assert n.is_legacy and n.is_final_order
    assert n.notice_no == "MCG/JC-2/DEMO/2023/0412"
    assert n.issued_at.date() == date(2023, 8, 14)
    assert "Joint Commissioner" in n.signer_name
    assert case.order_issued_at.date() == date(2023, 8, 14)
    assert case.compliance_due_at.date() == date(2023, 8, 29)          # order date + 15 days (not served yet)
    assert await events(db, case) == ["LEGACY_IMPORT", "LEGACY_STATUS"]
    assert (await run(db, verify_chain, case))["ok"]
    assert r.json()["legacy_reference"] == "Demolition order register 2023-24 p.61"
    assert "record_appeal" in r.json()["available_actions"]               # normal workflow continues (JC actions)
    assert (await get(db, m.Notice, notice_no="MCG/JC-2/DEMO/2023/0412")).case_id == case.id


async def test_import_served_order_gets_execution_due_when_period_over(db, client):
    jc = await officer(db, "JC")
    r = await client.post(f"{BASE}/legacy-orders/", json=await _order(db, order_no="MCG/JC-2/DEMO/2023/0413", served_on="2023-08-20", served_mode="AFFIXATION"), headers=hdr(jc))
    assert r.status_code == 201, r.text
    case = await _case(db, r.json()["id"])
    assert case.status == m.CaseStatus.EXECUTION_DUE
    assert case.order_served_at.date() == date(2023, 8, 20)
    assert case.compliance_due_at.date() == date(2023, 9, 4)          # served + 15 days
    assert await attr(db, case, "final_order.served_mode") == "AFFIXATION"


async def test_import_executed_order(db, client):
    jc = await officer(db, "JC")
    r = await client.post(f"{BASE}/legacy-orders/", json=await _order(db, order_no="MCG/JC-2/DEMO/2022/0099", order_date="2022-03-01", served_on="2022-03-05",
                                                                     executed_on="2022-04-02", execution_action="DEMOLITION", cost_incurred_inr="45000"), headers=hdr(jc))
    assert r.status_code == 201, r.text
    case = await _case(db, r.json()["id"])
    assert case.status == m.CaseStatus.EXECUTED
    ex = await get(db, m.ExecutionRecord, case_id=case.id)
    assert (ex.action, ex.mode, ex.executed_on.date()) == ("DEMOLITION", "CORPORATION", date(2022, 4, 2))
    assert str(case.demolition_cost_inr) == "45000.00"
    assert "close" in r.json()["available_actions"]


async def test_import_stayed_order(db, client):
    jc = await officer(db, "JC")
    r = await client.post(f"{BASE}/legacy-orders/", json=await _order(db, order_no="MCG/JC-2/DEMO/2024/0010", order_date="2024-01-10", served_on="2024-01-12",
                                                                     appeal_authority="HIGH_COURT", appeal_no="CWP 1234/2024", appeal_filed_on="2024-01-20",
                                                                     stay_granted=True, stay_order_date="2024-01-25"), headers=hdr(jc))
    assert r.status_code == 201, r.text
    case = await _case(db, r.json()["id"])
    assert (case.status, case.litigation_status, case.litigation_authority) == (m.CaseStatus.APPEAL_STAY, "STAYED", "HIGH_COURT")
    assert (await get(db, m.Appeal, case_id=case.id)).status == m.Appeal.Status.STAYED


async def test_import_closed_order_and_explicit_status(db, client):
    jc = await officer(db, "JC")
    r = await client.post(f"{BASE}/legacy-orders/", json=await _order(db, order_no="MCG/JC-2/DEMO/2021/0005", order_date="2021-06-01", current_status="REGULARISED",
                                                                     closed_on="2021-09-01", closure_reason="Compounded under s.256"), headers=hdr(jc))
    assert r.status_code == 201, r.text
    case = await _case(db, r.json()["id"])
    assert case.status == m.CaseStatus.REGULARISED
    assert case.closed_at.date() == date(2021, 9, 1)


# ---- guards ---------------------------------------------------------------------
async def test_duplicate_order_number_rejected(db, client):
    jc = await officer(db, "JC")
    assert (await client.post(f"{BASE}/legacy-orders/", json=await _order(db), headers=hdr(jc))).status_code == 201
    r = await client.post(f"{BASE}/legacy-orders/", json=await _order(db), headers=hdr(jc))
    assert r.status_code == 400
    assert "already on record" in r.json()["detail"]


async def test_je_cannot_import(db, client):
    je = await officer(db, "JE")
    assert (await client.post(f"{BASE}/legacy-orders/", json=await _order(db), headers=hdr(je))).status_code == 403


async def test_requires_order_no_date_and_property(db, client):
    jc = await officer(db, "JC")
    r = await client.post(f"{BASE}/legacy-orders/", json={**await _order(db), "pid": "", "address_line": ""}, headers=hdr(jc))
    assert r.status_code == 400
    r = await client.post(f"{BASE}/legacy-orders/", json={**await _order(db), "order_type": "SCN_261"}, headers=hdr(jc))
    assert r.status_code == 400


# ---- status updates from the paper file -----------------------------------------
async def test_update_status_from_paper_file(db, client):
    jc = await officer(db, "JC")
    case_id = (await client.post(f"{BASE}/legacy-orders/", json=await _order(db), headers=hdr(jc))).json()["id"]
    r = await client.post(f"{BASE}/legacy-orders/{case_id}/status/", json={"status": "ORDER_SERVED", "on_date": "2023-08-21", "served_mode": "IN_PERSON", "order_reference": "File 12/2023"}, headers=hdr(jc))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ORDER_SERVED"
    case = await _case(db, case_id)
    assert case.compliance_due_at.date() == date(2023, 9, 5)          # recomputed from service
    r = await client.post(f"{BASE}/legacy-orders/{case_id}/status/", json={"status": "APPEAL_STAY", "on_date": "2023-09-01", "appeal_authority": "DIVISIONAL_COMMISSIONER", "stay_until": "2024-03-31"}, headers=hdr(jc))
    assert r.status_code == 200, r.text
    await db.refresh(case)
    assert case.litigation_status == "STAYED"
    r = await client.post(f"{BASE}/legacy-orders/{case_id}/status/", json={"status": "ORDER_SERVED", "on_date": "2024-04-02", "remarks": "Stay vacated by order dated 1.4.2024"}, headers=hdr(jc))
    assert r.status_code == 200, r.text
    await db.refresh(case)
    assert (case.status, case.litigation_status) == ("ORDER_SERVED", "DECIDED")
    r = await client.post(f"{BASE}/legacy-orders/{case_id}/status/", json={"status": "EXECUTED", "on_date": "2024-05-10", "execution_action": "PARTIAL_DEMOLITION"}, headers=hdr(jc))
    assert r.status_code == 200, r.text
    await db.refresh(case)
    assert (case.status, case.executed_at.date()) == ("EXECUTED", date(2024, 5, 10))
    actions = await events(db, case)
    assert actions.count("LEGACY_STATUS") == 5
    remarks = await run(db, lambda s: [e.remarks for e in s.query(m.CaseEvent).filter_by(case_id=case.id, action="LEGACY_STATUS").order_by(m.CaseEvent.at, m.CaseEvent.id)])
    assert "File 12/2023" in remarks[1]
    # a normal (non-legacy) case cannot be short-cut this way
    normal = await run(db, lambda s: s.query(m.ViolationCase).filter(m.ViolationCase.source != "LEGACY_ORDER").first())
    if normal:
        assert (await client.post(f"{BASE}/legacy-orders/{normal.id}/status/", json={"status": "EXECUTED"}, headers=hdr(jc))).status_code == 404


# ---- bulk register -------------------------------------------------------------
async def test_bulk_import_from_register(db, client):
    jc, admin = await officer(db, "JC"), await officer(db, "ADMIN")
    tmpl = await client.get(f"{BASE}/legacy-orders/template/", headers=hdr(jc))
    assert tmpl.status_code == 200
    header = tmpl.text.splitlines()[0]
    rows = [header,
            "MCG/JC-3/DEMO/2022/0001,2022-02-01,DEMOLITION_ORDER_261,JC Zone 3,GGN098765,Plot 45 Sushant Lok,Sushant Lok,,,Suresh,9811100002,,Illegal 4th floor,15,2022-02-05,AFFIXATION,,,,,,,,,,,,Register 2022 p.3,",
            "MCG/JC-3/SEAL/2022/0002,2022-05-01,SEALING_263A,JC Zone 3,,Shop 4 Sadar Bazar,Sadar Bazar,,,Mahesh,,,Misuse,0,2022-05-02,IN_PERSON,,2022-05-03,SEALING,CORPORATION,,,,,,,Register 2022 p.9,",
            "MCG/JC-3/DEMO/2022/0003,not-a-date,DEMOLITION_ORDER_261,JC Zone 3,,Some address,,,,,,,,,,,,,,,,,,,,,,"]
    r = await client.post(f"{BASE}/legacy-orders/bulk/", data={"title": "Zone 3 register 2022", "order_reference": "Commissioner's order 44/2026"},
                          files={"file": ("register.csv", "\n".join(rows).encode(), "text/csv")}, headers=hdr(jc))
    assert r.status_code == 201, r.text
    assert (r.json()["total_rows"], r.json()["imported"], len(r.json()["errors"])) == (3, 2, 1)
    assert r.json()["errors"][0]["row"] == 4
    assert await run(db, lambda s: s.query(m.ViolationCase).filter_by(legacy_batch_id=r.json()["id"]).count()) == 2
    sealed = await run(db, lambda s: s.query(m.ViolationCase).join(m.Notice, m.ViolationCase.final_order_id == m.Notice.id).filter(m.Notice.notice_no == "MCG/JC-3/SEAL/2022/0002").one())
    assert (sealed.status, sealed.sealed) == (m.CaseStatus.EXECUTED, True)
    assert await run(db, lambda s: s.query(m.Notice).filter_by(is_legacy=True).count()) == 2
    # list, summary, register, dashboard
    r = await client.get(f"{BASE}/legacy-orders/", params={"status": "EXECUTION_DUE,EXECUTED"}, headers=hdr(jc))
    assert r.status_code == 200
    assert len(r.json()["results"]) == 2
    r = await client.get(f"{BASE}/legacy-orders/summary/", headers=hdr(jc))
    assert r.json()["total"] == 2
    r = await client.get(f"{BASE}/reports/legacy-orders/", headers=hdr(admin))
    assert len(r.json()["rows"]) == 2
    r = await client.get(f"{BASE}/dashboards/summary/", headers=hdr(admin))
    assert r.json()["legacy_orders_total"] == 2
    r = await client.get(f"{BASE}/legacy-orders/batches/", headers=hdr(jc))
    assert r.json()[0]["imported"] == 2
