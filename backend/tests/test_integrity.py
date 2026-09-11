"""Location-integrity (anti-GPS-spoofing) tests: device signals, admin switches, web uploads, teleport detection,
planned-inspection start, attestation requirement, pre-check endpoint and the register."""
import json
import uuid
from datetime import timedelta

import pytest

from app.core.timeutil import now
from app.models import building_violations as m
from app.services.building_violations import tasks as ts
from app.services.building_violations.location_integrity import consume_nonce
from tests.helpers import BASE, CLEAN, PNG, count, hdr, latest, officer, refresh, run, set_setting

pytestmark = pytest.mark.anyio


async def _upload(client, je, signals, lat="28.4700000", lng="77.0450000", **extra):
    data = {"kind": "INSPECTION", "latitude": lat, "longitude": lng, "accuracy_m": "8", "captured_at": now().isoformat(), "device_id": "test-device", **extra}
    if signals is not None:
        data["location_integrity"] = json.dumps(signals)
    return await client.post(f"{BASE}/media/", data=data, files={"file": ("site.png", PNG, "image/png")}, headers=hdr(je))


# ---- device signals -------------------------------------------------------------
async def test_clean_app_capture_passes(db, client):
    je = await officer(db, "JE")
    r = await _upload(client, je, CLEAN)
    assert r.status_code == 201, r.text
    assert r.json()["integrity_status"] == "PASS"
    chk = await run(db, lambda s: s.query(m.LocationIntegrityCheck).filter_by(media_id=uuid.UUID(r.json()["id"])).one())
    assert chk.decision == "PASS"
    assert chk.context == "MEDIA_UPLOAD"


async def test_mock_location_is_rejected_and_logged(db, client):
    je = await officer(db, "JE")
    n = await count(db, m.MediaAttachment)
    r = await _upload(client, je, {**CLEAN, "mock_location": True})
    assert r.status_code == 400
    assert "mock (fake) GPS" in r.json()["detail"]
    assert await count(db, m.MediaAttachment) == n                      # nothing stored as evidence
    chk = await latest(db, m.LocationIntegrityCheck)
    assert (chk.decision, chk.reasons) == ("REJECTED", ["MOCK_LOCATION"])


async def test_each_spoofing_signal_blocks_by_default(db, client):
    je = await officer(db, "JE")
    for field, value, code in (("simulated_by_software", True, "SIMULATED_LOCATION"), ("rooted", True, "ROOTED_DEVICE"), ("is_physical_device", False, "EMULATOR"),
                               ("developer_options", True, "DEVELOPER_OPTIONS"), ("vpn_active", True, "VPN_ACTIVE"), ("proxy_configured", True, "PROXY_CONFIGURED"),
                               ("fix_age_s", 900, "STALE_FIX")):
        r = await _upload(client, je, {**CLEAN, field: value})
        assert r.status_code == 400, field
        assert code in (await latest(db, m.LocationIntegrityCheck)).reasons, field


async def test_admin_can_turn_a_block_into_a_flag(db, client):
    je = await officer(db, "JE")
    await run(db, set_setting, "block_vpn_or_proxy", False)
    r = await _upload(client, je, {**CLEAN, "vpn_active": True})
    assert r.status_code == 201, r.text
    assert r.json()["integrity_status"] == "FLAGGED"
    assert "VPN_ACTIVE" in r.json()["integrity_reasons"]


async def test_poor_accuracy_only_flags(db, client):
    je = await officer(db, "JE")
    r = await _upload(client, je, CLEAN, accuracy_m="350")
    assert r.status_code == 201
    assert r.json()["integrity_status"] == "FLAGGED"
    assert "POOR_ACCURACY" in r.json()["integrity_reasons"]


# ---- browser / Expo Go ---------------------------------------------------------
async def test_browser_upload_is_flagged_by_default_and_blocked_when_configured(db, client):
    je = await officer(db, "JE")
    r = await _upload(client, je, {"source": "web", "platform": "web"})
    assert r.status_code == 201
    assert r.json()["integrity_status"] == "FLAGGED"
    assert "WEB_UNVERIFIED" in r.json()["integrity_reasons"]
    await run(db, set_setting, "block_web_geotags", True)
    r = await _upload(client, je, {"source": "web", "platform": "web"})
    assert r.status_code == 400
    assert "mobile app" in r.json()["detail"]


async def test_missing_signals_are_treated_as_unverified(db, client):
    je = await officer(db, "JE")
    r = await _upload(client, je, None)
    assert r.status_code == 201
    assert "NO_SIGNALS" in r.json()["integrity_reasons"]


async def test_expo_go_build_blocked_when_native_module_required(db, client):
    je = await officer(db, "JE")
    r = await _upload(client, je, {**CLEAN, "native_module": False})
    assert r.status_code == 201
    assert "NATIVE_CHECKS_UNAVAILABLE" in r.json()["integrity_reasons"]
    await run(db, set_setting, "require_native_integrity_module", True)
    r = await _upload(client, je, {**CLEAN, "native_module": False})
    assert r.status_code == 400
    assert "NO_NATIVE_INTEGRITY" in (await latest(db, m.LocationIntegrityCheck)).reasons


async def test_attestation_required(db, client):
    je = await officer(db, "JE")
    await run(db, set_setting, "require_device_attestation", True)
    r = await _upload(client, je, CLEAN)
    assert r.status_code == 400
    assert "ATTESTATION_MISSING" in (await latest(db, m.LocationIntegrityCheck)).reasons
    # a token the server cannot verify (no Google/Apple keys configured) is not accepted either
    r = await _upload(client, je, {**CLEAN, "attestation": {"type": "play_integrity", "token": "x", "nonce": "not-issued"}})
    assert r.status_code == 400
    chk = await latest(db, m.LocationIntegrityCheck)
    assert chk.attestation_status == "INVALID"
    assert "ATTESTATION_FAILED" in chk.reasons


async def test_nonce_is_single_use(db, client):
    je = await officer(db, "JE")
    n = (await client.post(f"{BASE}/integrity/nonce/", headers=hdr(je))).json()["nonce"]
    assert await run(db, consume_nonce, je, n) is True
    assert await run(db, consume_nonce, je, n) is False


# ---- server-side -----------------------------------------------------------------
async def test_teleport_between_consecutive_captures_is_rejected(db, client):
    je = await officer(db, "JE")
    assert (await _upload(client, je, CLEAN, lat="28.4700000", lng="77.0450000")).status_code == 201
    # 2 minutes later, 250 km away (Delhi -> Jaipur direction) -> impossible
    later = (now() + timedelta(minutes=2)).isoformat()
    r = await _upload(client, je, {**CLEAN, "fix_at": later}, lat="26.9124000", lng="75.7873000", captured_at=later)
    assert r.status_code == 400
    chk = await latest(db, m.LocationIntegrityCheck)
    assert "IMPLAUSIBLE_TRAVEL" in chk.reasons
    assert float(chk.travel_speed_kmph) > 1000
    # a normal move (3 km in 20 minutes) is fine
    later2 = (now() + timedelta(minutes=20)).isoformat()
    r = await _upload(client, je, {**CLEAN, "fix_at": later2}, lat="28.4950000", lng="77.0600000", captured_at=later2)
    assert r.status_code == 201, r.text


async def test_offline_upload_order_does_not_trigger_teleport(db, client):
    """A photo captured earlier at another site but uploaded later must be compared by fix time, not upload time."""
    je = await officer(db, "JE")
    assert (await _upload(client, je, CLEAN)).status_code == 201
    earlier = (now() - timedelta(hours=3)).isoformat()
    r = await _upload(client, je, {**CLEAN, "fix_at": earlier}, lat="28.6000000", lng="77.2000000", captured_at=earlier)   # 25 km, 3 h earlier
    assert r.status_code == 201, r.text


# ---- planned inspections & pre-check ----------------------------------------------
async def test_task_start_refused_with_mock_location(db, client):
    je, jc = await officer(db, "JE"), await officer(db, "JC")
    task = await run(db, ts.create_task, jc, pid="GGN012345", address="H.No. 123, Sector 14", latitude=28.47, longitude=77.045, assigned_to=je, lookup_pid=False)
    body = {"latitude": str(task.latitude), "longitude": str(task.longitude), "accuracy_m": 5, "location_integrity": {**CLEAN, "mock_location": True}}
    r = await client.post(f"{BASE}/inspections/tasks/{task.id}/start/", json=body, headers=hdr(je))
    assert r.status_code == 400
    await refresh(db, task)
    assert task.status != m.InspectionTask.Status.IN_PROGRESS
    body["location_integrity"] = CLEAN
    r = await client.post(f"{BASE}/inspections/tasks/{task.id}/start/", json=body, headers=hdr(je))
    assert r.status_code == 200, r.text
    assert r.json()["start_integrity"]["decision"] == "PASS"


async def test_precheck_reports_without_blocking(db, client):
    je = await officer(db, "JE")
    r = await client.post(f"{BASE}/integrity/precheck/", json={"latitude": "28.47", "longitude": "77.045", "accuracy_m": 6, "location_integrity": {**CLEAN, "rooted": True, "vpn_active": True}}, headers=hdr(je))
    assert r.status_code == 200
    assert r.json()["decision"] == "REJECTED"
    assert set(r.json()["reasons"]) == {"ROOTED_DEVICE", "VPN_ACTIVE"}
    assert r.json()["advice"]
    assert await count(db, m.LocationIntegrityCheck, context="PRECHECK") == 1


async def test_register_and_dashboard(db, client):
    je, admin = await officer(db, "JE"), await officer(db, "ADMIN")
    await _upload(client, je, {**CLEAN, "mock_location": True})
    r = await client.get(f"{BASE}/reports/location-integrity/", params={"decision": "REJECTED"}, headers=hdr(admin))
    assert r.status_code == 200
    assert len(r.json()["rows"]) == 1
    assert "MOCK_LOCATION" in r.json()["rows"][0][r.json()["columns"].index("reasons")]
    r = await client.get(f"{BASE}/integrity/checks/summary/", headers=hdr(admin))
    assert r.status_code == 200, r.text
    assert r.json()["rejected"] == 1
    assert r.json()["reasons"][0]["code"] == "MOCK_LOCATION"
    r = await client.get(f"{BASE}/dashboards/summary/", headers=hdr(admin))
    assert r.json()["integrity_rejected_30d"] == 1
