"""Input validation that the clients rely on: the alternate mobile number is stored as exactly 10 digits."""
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
