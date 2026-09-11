"""Planned inspections with geofence, bulk push of PIDs, GIS-lab layer versioning (GeoJSON/KML), map payloads."""
import io
import json
import zipfile

import pytest

from app.models import building_violations as m
from app.services.building_violations import tasks as ts
from app.services.building_violations import workflow as wf
from tests.helpers import BASE, PNG, add_media, get, hdr, officer, refresh, run, ward

pytestmark = pytest.mark.anyio

KML = b'''<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>Community site 12</name><ExtendedData><Data name="khasra"><value>221</value></Data><Data name="village"><value>Chakkarpur</value></Data></ExtendedData><Polygon><outerBoundaryIs><LinearRing><coordinates>77.0900,28.4700,0 77.0920,28.4700,0 77.0920,28.4720,0 77.0900,28.4720,0 77.0900,28.4700,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>'''


# ---- planned inspections ---------------------------------------------
async def test_jc_pushes_pid_and_je_must_be_within_100m(db):
    je, jc = await officer(db, "JE"), await officer(db, "JC")
    t = await run(db, ts.create_task, jc, pid="GGN012345", category="PG_HOSTEL", instructions="Verify PG", assigned_to=je, lookup_pid=True)
    assert t.status == "ASSIGNED"
    assert float(t.latitude) == 28.47          # filled from the PID record
    assert t.owner_mobile == "9811100001"
    assert t.geofence_m == 100
    with pytest.raises(wf.WorkflowError) as cm:
        await run(db, ts.start_task, t, je, latitude=28.4800, longitude=77.0450)   # ~1.1 km away
    assert "move within 100 m" in str(cm.value)
    await run(db, ts.start_task, t, je, latitude=28.47040, longitude=77.04520)   # ~50 m
    assert t.status == "IN_PROGRESS"
    assert float(t.start_distance_m) < 100
    # recording the case from the task also needs the officer on site
    with pytest.raises(wf.WorkflowError):
        await run(db, wf.create_case, je, dict(address_line="x", description="PG found", task=t, inspector_latitude=28.49, inspector_longitude=77.05), [{"code": "MU-01"}])
    case = await run(db, wf.create_case, je, dict(address_line="x", description="PG with 14 rooms, no CLU", task=t, inspector_latitude=28.47035, inspector_longitude=77.04515), [{"code": "MU-01"}])
    await refresh(db, t)
    assert t.status == "VIOLATION_RECORDED"
    assert case.task_id == t.id
    assert case.pid == "GGN012345"
    assert case.inspector_distance_m is not None


async def test_no_violation_closure_requires_photo_on_site(db):
    je, jc = await officer(db, "JE"), await officer(db, "JC")
    t = await run(db, ts.create_task, jc, address="Plot 5", latitude=28.4665, longitude=77.0410, assigned_to=je)
    await run(db, ts.start_task, t, je, latitude=28.4666, longitude=77.0411)
    with pytest.raises(wf.WorkflowError):
        await run(db, ts.complete_task_no_violation, t, je, outcome="NO_VIOLATION", remarks="ok", media_ids=[])
    mm = await run(db, add_media, None, 28.4666, 77.0411, je, "TASK_EVIDENCE")
    await run(db, ts.complete_task_no_violation, t, je, outcome="NO_VIOLATION", remarks="Residential use, no PG", media_ids=[mm.id], latitude=28.4666, longitude=77.0411)
    assert t.status == "NO_VIOLATION"
    await refresh(db, mm)
    assert mm.task_id == t.id
    assert mm.geotag_verified is True


async def test_bulk_upload_and_api_scoping(db, client):
    je, jc = await officer(db, "JE"), await officer(db, "JC")
    csv = b"pid,address,latitude,longitude,ward_number,owner_name,owner_mobile,category,instructions,priority,assign_to_mobile\nGGN012345,H.No. 123 Sector 14,28.47,77.045,19,Ramesh,9811100001,PG_HOSTEL,Check PG,HIGH,9000000001\n,Plot 9 Sector 15,28.466,77.041,19,,,DRONE_FLAG,New slab,NORMAL,\n,,,,,,,,,,\n"
    r = await client.post(f"{BASE}/inspections/tasks/bulk_upload/", data={"title": "PG drive", "category": "PG_HOSTEL", "due_days": "5", "lookup_pid": "0"}, files={"file": ("pg.csv", csv, "text/csv")}, headers=hdr(jc))
    assert r.status_code == 201, r.text
    assert r.json()["total"] == 2
    assert len(r.json()["errors"]) == 1  # the empty row
    # JE sees only own / ward-pool tasks; JC sees all
    mine = (await client.get(f"{BASE}/inspections/tasks/", params={"mine": "1"}, headers=hdr(je))).json()["count"]
    assert mine >= 1
    # distance pre-check and start via API
    tid = (await client.get(f"{BASE}/inspections/tasks/", params={"mine": "1", "search": "GGN012345"}, headers=hdr(je))).json()["results"][0]["id"]
    d = (await client.get(f"{BASE}/inspections/tasks/{tid}/distance/", params={"lat": 28.47, "lng": 77.045}, headers=hdr(je))).json()
    assert d["within"] is True
    r = await client.post(f"{BASE}/inspections/tasks/{tid}/start/", json={"latitude": 28.48, "longitude": 77.045}, headers=hdr(je))
    assert r.status_code == 400
    r = await client.post(f"{BASE}/inspections/tasks/{tid}/start/", json={"latitude": 28.4701, "longitude": 77.0451}, headers=hdr(je))
    assert r.status_code == 200, r.text
    # JE cannot push tasks
    assert (await client.post(f"{BASE}/inspections/tasks/", json={"pid": "GGN098765"}, headers=hdr(je))).status_code == 403
    # report
    assert (await client.get(f"{BASE}/reports/planned-inspections/", headers=hdr(jc))).status_code == 200


# ---- GIS lab ---------------------------------------------------------
async def test_gis_lab_uploads_kml_and_versioning(db, client):
    gis, je = await officer(db, "GIS_LAB"), await officer(db, "JE")
    r = await client.post(f"{BASE}/gis/land-layers/", data={"name": "HSVP community sites", "layer_key": "hsvp-community-sites", "agency": "HSVP", "source": "HSVP layout plan", "order_reference": "GIS/2026/5"},
                          files={"source_file": ("sites.kml", KML, "application/vnd.google-earth.kml+xml")}, headers=hdr(gis))
    assert r.status_code == 201, r.text
    assert r.json()["feature_count"] == 1
    assert r.json()["file_format"] == "KML"
    p = await get(db, m.GovtLandParcel, layer_key="hsvp-community-sites")
    assert p.khasra_no == "221"
    assert p.village == "Chakkarpur"
    # point inside the new parcel is detected
    chk = (await client.get(f"{BASE}/gis/check-point/", params={"lat": 28.471, "lng": 77.091}, headers=hdr(gis))).json()
    assert chk["land_type"] == "GOVT_STATE"
    # re-upload -> version 2, v1 retired
    gj = json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "Community site 12 (revised)", "KHASRA": "221/1"}, "geometry": {"type": "Polygon", "coordinates": [[[77.0900, 28.4700], [77.0930, 28.4700], [77.0930, 28.4725], [77.0900, 28.4725], [77.0900, 28.4700]]]}}]}).encode()
    r = await client.post(f"{BASE}/gis/land-layers/", data={"name": "HSVP community sites", "layer_key": "hsvp-community-sites", "agency": "HSVP"}, files={"source_file": ("sites.geojson", gj, "application/geo+json")}, headers=hdr(gis))
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 2
    assert await run(db, lambda s: s.query(m.GovtLandParcel).filter_by(layer_key="hsvp-community-sites", active=True).count()) == 1
    v1 = await run(db, lambda s: s.query(m.LandLayerUpload).filter_by(version=1, layer_key="hsvp-community-sites").one())
    assert v1.active is False
    # projected shapefile is rejected with a clear message
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.shp", b"\x00" * 100)
        z.writestr("x.dbf", b"\x00" * 100)
        z.writestr("x.prj", 'PROJCS["WGS_1984_UTM_Zone_43N",GEOGCS["GCS_WGS_1984"]]')
    r = await client.post(f"{BASE}/gis/land-layers/", data={"name": "bad", "layer_key": "bad", "agency": "MCG"}, files={"source_file": ("x.zip", buf.getvalue(), "application/zip")}, headers=hdr(gis))
    assert r.status_code == 400
    assert "EPSG:4326" in r.json()["detail"]
    # a JE cannot upload layers
    assert (await client.post(f"{BASE}/gis/land-layers/", data={"name": "x", "layer_key": "x", "agency": "MCG"}, files={"source_file": ("a.kml", KML)}, headers=hdr(je))).status_code == 403


async def test_map_payloads_carry_status_and_history(db, client):
    je, ae, jc = [await officer(db, r) for r in ("JE", "AE", "JC")]
    w = await ward(db, 19)
    case = await run(db, wf.create_case, je, dict(address_line="Shed on green belt", latitude=28.4700, longitude=77.0455, description="tin shed", ward=w), [{"code": "GL-01"}])
    await run(db, add_media, case, 28.47, 77.0455, je)
    await run(db, wf.submit_to_ae, case, je)
    await run(db, wf.ae_forward, case, ae)
    await run(db, wf.jc_issue_notice, case, jc, order_type_code="SCN_408A")
    await run(db, ts.create_task, jc, address="Plot 9", latitude=28.466, longitude=77.041, assigned_to=je)
    mp = (await client.get(f"{BASE}/dashboards/map/", params={"tasks": "1"}, headers=hdr(jc))).json()
    pin = next(f for f in mp["features"] if f["properties"].get("case_no") == case.case_no)
    assert pin["properties"]["status"] == "SCN_ISSUED"
    assert len(pin["properties"]["history"]) >= 4
    assert any(f["properties"]["kind"] == "task" for f in mp["features"])
    land = (await client.get(f"{BASE}/gis/govt-land/geojson/", headers=hdr(jc))).json()
    parcel = next(f for f in land["features"] if f["properties"]["name"].startswith("Green belt"))
    assert parcel["properties"]["open_case_count"] == 1
    assert parcel["properties"]["cases"][0]["status"] == "SCN_ISSUED"
