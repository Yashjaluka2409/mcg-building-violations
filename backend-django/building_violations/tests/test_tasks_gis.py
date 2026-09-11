"""Planned inspections with geofence, bulk push of PIDs, GIS-lab layer versioning (GeoJSON/KML), map payloads."""
import io
import json
import zipfile

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from building_violations.models import GovtLandParcel, InspectionTask, LandLayerUpload, MediaAttachment, OfficerProfile, Role, Ward
from building_violations.services import access
from building_violations.services import tasks as ts
from building_violations.services import workflow as wf

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
KML = b'''<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>Community site 12</name><ExtendedData><Data name="khasra"><value>221</value></Data><Data name="village"><value>Chakkarpur</value></Data></ExtendedData><Polygon><outerBoundaryIs><LinearRing><coordinates>77.0900,28.4700,0 77.0920,28.4700,0 77.0920,28.4720,0 77.0900,28.4720,0 77.0900,28.4700,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>'''


class TasksAndGISTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.je = OfficerProfile.objects.get(role=Role.JE).user
        cls.jc = OfficerProfile.objects.get(role=Role.JC).user
        cls.gis = OfficerProfile.objects.get(role=Role.GIS_LAB).user
        cls.ae = OfficerProfile.objects.get(role=Role.AE).user

    def setUp(self):
        access.invalidate()

    def _media(self, user, lat, lng, task=None):
        mm = MediaAttachment(task=task, kind="TASK_EVIDENCE", media_type="IMAGE", latitude=lat, longitude=lng, accuracy_m=5, captured_at=timezone.now(), uploaded_by=user)
        mm.file.save("x.png", ContentFile(PNG), save=True)
        return mm

    # ---- planned inspections ---------------------------------------------
    def test_jc_pushes_pid_and_je_must_be_within_100m(self):
        t = ts.create_task(self.jc, pid="GGN012345", category="PG_HOSTEL", instructions="Verify PG", assigned_to=self.je, lookup_pid=True)
        self.assertEqual(t.status, "ASSIGNED")
        self.assertEqual(float(t.latitude), 28.47)          # filled from the PID record
        self.assertEqual(t.owner_mobile, "9811100001")
        self.assertEqual(t.geofence_m, 100)
        with self.assertRaises(wf.WorkflowError) as cm:
            ts.start_task(t, self.je, latitude=28.4800, longitude=77.0450)   # ~1.1 km away
        self.assertIn("move within 100 m", str(cm.exception))
        ts.start_task(t, self.je, latitude=28.47040, longitude=77.04520)   # ~50 m
        self.assertEqual(t.status, "IN_PROGRESS")
        self.assertLess(float(t.start_distance_m), 100)
        # recording the case from the task also needs the officer on site
        with self.assertRaises(wf.WorkflowError):
            wf.create_case(self.je, dict(address_line="x", description="PG found", task=t, inspector_latitude=28.49, inspector_longitude=77.05), [{"code": "MU-01"}])
        case = wf.create_case(self.je, dict(address_line="x", description="PG with 14 rooms, no CLU", task=t, inspector_latitude=28.47035, inspector_longitude=77.04515), [{"code": "MU-01"}])
        t.refresh_from_db()
        self.assertEqual(t.status, "VIOLATION_RECORDED")
        self.assertEqual(case.task_id, t.id)
        self.assertEqual(case.pid, "GGN012345")
        self.assertIsNotNone(case.inspector_distance_m)

    def test_no_violation_closure_requires_photo_on_site(self):
        t = ts.create_task(self.jc, address="Plot 5", latitude=28.4665, longitude=77.0410, assigned_to=self.je)
        ts.start_task(t, self.je, latitude=28.4666, longitude=77.0411)
        with self.assertRaises(wf.WorkflowError):
            ts.complete_task_no_violation(t, self.je, outcome="NO_VIOLATION", remarks="ok", media_ids=[])
        m = self._media(self.je, 28.4666, 77.0411)
        ts.complete_task_no_violation(t, self.je, outcome="NO_VIOLATION", remarks="Residential use, no PG", media_ids=[m.id], latitude=28.4666, longitude=77.0411)
        self.assertEqual(t.status, "NO_VIOLATION")
        m.refresh_from_db()
        self.assertEqual(m.task_id, t.id)
        self.assertTrue(m.geotag_verified)

    def test_bulk_upload_and_api_scoping(self):
        c = APIClient(); c.force_authenticate(self.jc)
        csv = b"pid,address,latitude,longitude,ward_number,owner_name,owner_mobile,category,instructions,priority,assign_to_mobile\nGGN012345,H.No. 123 Sector 14,28.47,77.045,19,Ramesh,9811100001,PG_HOSTEL,Check PG,HIGH,9000000001\n,Plot 9 Sector 15,28.466,77.041,19,,,DRONE_FLAG,New slab,NORMAL,\n,,,,,,,,,,\n"
        r = c.post("/building-violations/api/inspections/tasks/bulk_upload/", {"file": SimpleUploadedFile("pg.csv", csv, content_type="text/csv"), "title": "PG drive", "category": "PG_HOSTEL", "due_days": 5, "lookup_pid": "0"}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["total"], 2)
        self.assertEqual(len(r.json()["errors"]), 1)  # the empty row
        # JE sees only own / ward-pool tasks; JC sees all
        j = APIClient(); j.force_authenticate(self.je)
        mine = j.get("/building-violations/api/inspections/tasks/", {"mine": "1"}).json()["count"]
        self.assertGreaterEqual(mine, 1)
        # distance pre-check and start via API
        tid = j.get("/building-violations/api/inspections/tasks/", {"mine": "1", "search": "GGN012345"}).json()["results"][0]["id"]
        d = j.get(f"/building-violations/api/inspections/tasks/{tid}/distance/", {"lat": 28.47, "lng": 77.045}).json()
        self.assertTrue(d["within"])
        r = j.post(f"/building-violations/api/inspections/tasks/{tid}/start/", {"latitude": 28.48, "longitude": 77.045}, format="json")
        self.assertEqual(r.status_code, 400)
        r = j.post(f"/building-violations/api/inspections/tasks/{tid}/start/", {"latitude": 28.4701, "longitude": 77.0451}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        # JE cannot push tasks
        self.assertEqual(j.post("/building-violations/api/inspections/tasks/", {"pid": "GGN098765"}, format="json").status_code, 403)
        # report
        self.assertEqual(c.get("/building-violations/api/reports/planned-inspections/").status_code, 200)

    # ---- GIS lab ---------------------------------------------------------
    def test_gis_lab_uploads_kml_and_versioning(self):
        g = APIClient(); g.force_authenticate(self.gis)
        r = g.post("/building-violations/api/gis/land-layers/", {"name": "HSVP community sites", "layer_key": "hsvp-community-sites", "agency": "HSVP", "source": "HSVP layout plan", "source_file": SimpleUploadedFile("sites.kml", KML, content_type="application/vnd.google-earth.kml+xml"), "order_reference": "GIS/2026/5"}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["feature_count"], 1)
        self.assertEqual(r.json()["file_format"], "KML")
        p = GovtLandParcel.objects.get(layer_key="hsvp-community-sites")
        self.assertEqual(p.khasra_no, "221")
        self.assertEqual(p.village, "Chakkarpur")
        # point inside the new parcel is detected
        chk = g.get("/building-violations/api/gis/check-point/", {"lat": 28.471, "lng": 77.091}).json()
        self.assertEqual(chk["land_type"], "GOVT_STATE")
        # re-upload -> version 2, v1 retired
        gj = json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "Community site 12 (revised)", "KHASRA": "221/1"}, "geometry": {"type": "Polygon", "coordinates": [[[77.0900, 28.4700], [77.0930, 28.4700], [77.0930, 28.4725], [77.0900, 28.4725], [77.0900, 28.4700]]]}}]}).encode()
        r = g.post("/building-violations/api/gis/land-layers/", {"name": "HSVP community sites", "layer_key": "hsvp-community-sites", "agency": "HSVP", "source_file": SimpleUploadedFile("sites.geojson", gj, content_type="application/geo+json")}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["version"], 2)
        self.assertEqual(GovtLandParcel.objects.filter(layer_key="hsvp-community-sites", active=True).count(), 1)
        self.assertFalse(LandLayerUpload.objects.get(version=1, layer_key="hsvp-community-sites").active)
        # projected shapefile is rejected with a clear message
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("x.shp", b"\x00" * 100); z.writestr("x.dbf", b"\x00" * 100); z.writestr("x.prj", 'PROJCS["WGS_1984_UTM_Zone_43N",GEOGCS["GCS_WGS_1984"]]')
        r = g.post("/building-violations/api/gis/land-layers/", {"name": "bad", "layer_key": "bad", "agency": "MCG", "source_file": SimpleUploadedFile("x.zip", buf.getvalue(), content_type="application/zip")}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("EPSG:4326", r.json()["detail"])
        # a JE cannot upload layers
        j = APIClient(); j.force_authenticate(self.je)
        self.assertEqual(j.post("/building-violations/api/gis/land-layers/", {"name": "x", "layer_key": "x", "agency": "MCG", "source_file": SimpleUploadedFile("a.kml", KML)}, format="multipart").status_code, 403)

    def test_map_payloads_carry_status_and_history(self):
        case = wf.create_case(self.je, dict(address_line="Shed on green belt", latitude=28.4700, longitude=77.0455, description="tin shed", ward=Ward.objects.get(number=19)), [{"code": "GL-01"}])
        mm = MediaAttachment(case=case, kind="INSPECTION", media_type="IMAGE", latitude=28.47, longitude=77.0455, uploaded_by=self.je); mm.file.save("x.png", ContentFile(PNG), save=True)
        wf.attach_media(case, [mm.id], self.je)
        wf.submit_to_ae(case, self.je); wf.ae_forward(case, self.ae)
        wf.jc_issue_notice(case, self.jc, order_type_code="SCN_408A")
        ts.create_task(self.jc, address="Plot 9", latitude=28.466, longitude=77.041, assigned_to=self.je)
        c = APIClient(); c.force_authenticate(self.jc)
        mp = c.get("/building-violations/api/dashboards/map/", {"tasks": "1"}).json()
        pin = next(f for f in mp["features"] if f["properties"].get("case_no") == case.case_no)
        self.assertEqual(pin["properties"]["status"], "SCN_ISSUED")
        self.assertGreaterEqual(len(pin["properties"]["history"]), 4)
        self.assertTrue(any(f["properties"]["kind"] == "task" for f in mp["features"]))
        land = c.get("/building-violations/api/gis/govt-land/geojson/").json()
        parcel = next(f for f in land["features"] if f["properties"]["name"].startswith("Green belt"))
        self.assertEqual(parcel["properties"]["open_case_count"], 1)
        self.assertEqual(parcel["properties"]["cases"][0]["status"], "SCN_ISSUED")
