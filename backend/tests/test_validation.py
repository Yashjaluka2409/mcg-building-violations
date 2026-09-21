"""Input validation that the clients rely on: 10-digit alternate mobile, occupancy head-counts."""
import pytest

from tests.helpers import BASE, hdr, officer, ward

pytestmark = pytest.mark.anyio


def _draft(w, **over):
    data = dict(pid="GGN012345", address_line="H.No. 5, Sector 15", latitude=28.4700, longitude=77.0450, owner_name="Test Owner",
                description="draft", ward=w.id, violations=[{"code": "DV-03"}], submit=False)
    data.update(over)
    return data


async def test_alternate_mobile_must_be_10_digits(client, db):
    je = await officer(db, "JE")
    w = await ward(db, 19)
    for bad in ("12345", "98765abcde", "abc", "98765432101"):
        r = await client.post(f"{BASE}/cases/", json=_draft(w, alternate_mobile=bad), headers=hdr(je))
        assert r.status_code == 400, (bad, r.text)
        assert "alternate_mobile" in r.json(), r.text
        assert "10-digit" in r.json()["alternate_mobile"][0]


async def test_alternate_mobile_is_normalised_to_10_digits(client, db):
    je = await officer(db, "JE")
    w = await ward(db, 19)
    r = await client.post(f"{BASE}/cases/", json=_draft(w, alternate_mobile="+91 98765 43210"), headers=hdr(je))
    assert r.status_code == 201, r.text
    assert r.json()["alternate_mobile"] == "9876543210"
    r = await client.post(f"{BASE}/cases/", json=_draft(w, alternate_mobile=""), headers=hdr(je))
    assert r.status_code == 201, r.text
    assert r.json()["alternate_mobile"] == ""


async def test_occupancy_is_recorded_and_returned(client, db):
    je = await officer(db, "JE")
    w = await ward(db, 19)
    r = await client.post(f"{BASE}/cases/", headers=hdr(je), json=_draft(
        w, use_observed="PG / hostel", occupants_total="24", occupants_senior_citizens=2, occupants_children="", occupants_women=9))
    assert r.status_code == 201, r.text
    c = r.json()
    assert (c["use_observed"], c["occupants_total"], c["occupants_senior_citizens"], c["occupants_children"], c["occupants_women"]) == ("PG / hostel", 24, 2, None, 9)
    r = await client.patch(f"{BASE}/cases/{c['id']}/", headers=hdr(je), json={"occupants_children": 5})
    assert r.status_code == 200, r.text
    assert r.json()["occupants_children"] == 5
    r = await client.patch(f"{BASE}/cases/{c['id']}/", headers=hdr(je), json={"occupants_women": 30})
    assert r.status_code == 400, r.text


async def test_occupancy_groups_cannot_exceed_total(client, db):
    je = await officer(db, "JE")
    w = await ward(db, 19)
    for bad, key in (({"occupants_total": 4, "occupants_women": 5}, "occupants_women"), ({"occupants_total": 4, "occupants_senior_citizens": 3, "occupants_children": 2}, "occupants_children"),
                     ({"occupants_total": -1}, "occupants_total"), ({"occupants_total": "many"}, "occupants_total")):
        r = await client.post(f"{BASE}/cases/", headers=hdr(je), json=_draft(w, **bad))
        assert r.status_code == 400, (bad, r.text)
        assert key in r.json(), r.text
