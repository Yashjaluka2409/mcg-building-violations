"""Location-integrity (anti-GPS-spoofing) tests: device signals, admin switches, web uploads, teleport detection,
planned-inspection start, attestation requirement, pre-check endpoint and the register."""
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from building_violations.models import InspectionTask, LocationIntegrityCheck, MediaAttachment, OfficerProfile, Role, WorkflowSetting
from building_violations.services import access

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00"
       b"\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

CLEAN = {"source": "app", "platform": "android", "native_module": True, "is_physical_device": True, "rooted": False, "developer_options": False,
         "mock_location": False, "vpn_active": False, "proxy_configured": False, "fix_age_s": 2, "jitter_m": 0.8, "app_version": "1.0.0", "device_model": "Pixel 8"}


def _set(key, value):
    WorkflowSetting.objects.filter(key=key).update(value=value)
    access.invalidate()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class IntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.je = OfficerProfile.objects.get(role=Role.JE).user

    def setUp(self):
        access.invalidate()
        self.c = APIClient()
        self.c.force_authenticate(self.je)

    def _upload(self, signals, lat="28.4700000", lng="77.0450000", **extra):
        from django.core.files.uploadedfile import SimpleUploadedFile
        data = {"file": SimpleUploadedFile("site.png", PNG, content_type="image/png"), "kind": "INSPECTION", "latitude": lat, "longitude": lng,
                "accuracy_m": "8", "captured_at": timezone.now().isoformat(), "device_id": "test-device", **extra}
        if signals is not None:
            import json
            data["location_integrity"] = json.dumps(signals)
        return self.c.post("/building-violations/api/media/", data, format="multipart")

    # ---- device signals -------------------------------------------------------------
    def test_clean_app_capture_passes(self):
        r = self._upload(CLEAN)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["integrity_status"], "PASS")
        chk = LocationIntegrityCheck.objects.get(media_id=r.data["id"])
        self.assertEqual(chk.decision, "PASS")
        self.assertEqual(chk.context, "MEDIA_UPLOAD")

    def test_mock_location_is_rejected_and_logged(self):
        n = MediaAttachment.objects.count()
        r = self._upload({**CLEAN, "mock_location": True})
        self.assertEqual(r.status_code, 400)
        self.assertIn("mock (fake) GPS", r.data["detail"])
        self.assertEqual(MediaAttachment.objects.count(), n)                      # nothing stored as evidence
        chk = LocationIntegrityCheck.objects.latest("at")
        self.assertEqual((chk.decision, chk.reasons), ("REJECTED", ["MOCK_LOCATION"]))

    def test_each_spoofing_signal_blocks_by_default(self):
        for field, value, code in (("simulated_by_software", True, "SIMULATED_LOCATION"), ("rooted", True, "ROOTED_DEVICE"), ("is_physical_device", False, "EMULATOR"),
                                   ("developer_options", True, "DEVELOPER_OPTIONS"), ("vpn_active", True, "VPN_ACTIVE"), ("proxy_configured", True, "PROXY_CONFIGURED"),
                                   ("fix_age_s", 900, "STALE_FIX")):
            r = self._upload({**CLEAN, field: value})
            self.assertEqual(r.status_code, 400, field)
            self.assertIn(code, LocationIntegrityCheck.objects.latest("at").reasons, field)

    def test_admin_can_turn_a_block_into_a_flag(self):
        _set("block_vpn_or_proxy", False)
        r = self._upload({**CLEAN, "vpn_active": True})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["integrity_status"], "FLAGGED")
        self.assertIn("VPN_ACTIVE", r.data["integrity_reasons"])

    def test_poor_accuracy_only_flags(self):
        r = self._upload(CLEAN, accuracy_m="350")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["integrity_status"], "FLAGGED")
        self.assertIn("POOR_ACCURACY", r.data["integrity_reasons"])

    # ---- browser / Expo Go ---------------------------------------------------------
    def test_browser_upload_is_flagged_by_default_and_blocked_when_configured(self):
        r = self._upload({"source": "web", "platform": "web"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["integrity_status"], "FLAGGED")
        self.assertIn("WEB_UNVERIFIED", r.data["integrity_reasons"])
        _set("block_web_geotags", True)
        r = self._upload({"source": "web", "platform": "web"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("mobile app", r.data["detail"])

    def test_missing_signals_are_treated_as_unverified(self):
        r = self._upload(None)
        self.assertEqual(r.status_code, 201)
        self.assertIn("NO_SIGNALS", r.data["integrity_reasons"])

    def test_expo_go_build_blocked_when_native_module_required(self):
        r = self._upload({**CLEAN, "native_module": False})
        self.assertEqual(r.status_code, 201)
        self.assertIn("NATIVE_CHECKS_UNAVAILABLE", r.data["integrity_reasons"])
        _set("require_native_integrity_module", True)
        r = self._upload({**CLEAN, "native_module": False})
        self.assertEqual(r.status_code, 400)
        self.assertIn("NO_NATIVE_INTEGRITY", LocationIntegrityCheck.objects.latest("at").reasons)

    def test_attestation_required(self):
        _set("require_device_attestation", True)
        r = self._upload(CLEAN)
        self.assertEqual(r.status_code, 400)
        self.assertIn("ATTESTATION_MISSING", LocationIntegrityCheck.objects.latest("at").reasons)
        # a token the server cannot verify (no Google/Apple keys configured) is not accepted either
        r = self._upload({**CLEAN, "attestation": {"type": "play_integrity", "token": "x", "nonce": "not-issued"}})
        self.assertEqual(r.status_code, 400)
        chk = LocationIntegrityCheck.objects.latest("at")
        self.assertEqual(chk.attestation_status, "INVALID")
        self.assertIn("ATTESTATION_FAILED", chk.reasons)

    def test_nonce_is_single_use(self):
        n = self.c.post("/building-violations/api/integrity/nonce/").data["nonce"]
        from building_violations.services.location_integrity import consume_nonce
        self.assertTrue(consume_nonce(self.je, n))
        self.assertFalse(consume_nonce(self.je, n))

    # ---- server-side -----------------------------------------------------------------
    def test_teleport_between_consecutive_captures_is_rejected(self):
        self.assertEqual(self._upload(CLEAN, lat="28.4700000", lng="77.0450000").status_code, 201)
        # 2 minutes later, 250 km away (Delhi -> Jaipur direction) -> impossible
        later = (timezone.now() + timedelta(minutes=2)).isoformat()
        r = self._upload({**CLEAN, "fix_at": later}, lat="26.9124000", lng="75.7873000", captured_at=later)
        self.assertEqual(r.status_code, 400)
        chk = LocationIntegrityCheck.objects.latest("at")
        self.assertIn("IMPLAUSIBLE_TRAVEL", chk.reasons)
        self.assertGreater(float(chk.travel_speed_kmph), 1000)
        # a normal move (3 km in 20 minutes) is fine
        later2 = (timezone.now() + timedelta(minutes=20)).isoformat()
        r = self._upload({**CLEAN, "fix_at": later2}, lat="28.4950000", lng="77.0600000", captured_at=later2)
        self.assertEqual(r.status_code, 201, r.content)

    def test_offline_upload_order_does_not_trigger_teleport(self):
        """A photo captured earlier at another site but uploaded later must be compared by fix time, not upload time."""
        self.assertEqual(self._upload(CLEAN).status_code, 201)
        earlier = (timezone.now() - timedelta(hours=3)).isoformat()
        r = self._upload({**CLEAN, "fix_at": earlier}, lat="28.6000000", lng="77.2000000", captured_at=earlier)   # 25 km, 3 h earlier
        self.assertEqual(r.status_code, 201, r.content)

    # ---- planned inspections & pre-check ----------------------------------------------
    def test_task_start_refused_with_mock_location(self):
        from building_violations.services import tasks as ts
        jc = OfficerProfile.objects.filter(role=Role.JC).first().user
        task = ts.create_task(jc, pid="GGN012345", address="H.No. 123, Sector 14", latitude=28.47, longitude=77.045, assigned_to=self.je, lookup_pid=False)
        body = {"latitude": str(task.latitude), "longitude": str(task.longitude), "accuracy_m": 5, "location_integrity": {**CLEAN, "mock_location": True}}
        r = self.c.post(f"/building-violations/api/inspections/tasks/{task.id}/start/", body, format="json")
        self.assertEqual(r.status_code, 400)
        task.refresh_from_db()
        self.assertNotEqual(task.status, InspectionTask.Status.IN_PROGRESS)
        body["location_integrity"] = CLEAN
        r = self.c.post(f"/building-violations/api/inspections/tasks/{task.id}/start/", body, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["start_integrity"]["decision"], "PASS")

    def test_precheck_reports_without_blocking(self):
        r = self.c.post("/building-violations/api/integrity/precheck/", {"latitude": "28.47", "longitude": "77.045", "accuracy_m": 6,
                                                                          "location_integrity": {**CLEAN, "rooted": True, "vpn_active": True}}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["decision"], "REJECTED")
        self.assertEqual(set(r.data["reasons"]), {"ROOTED_DEVICE", "VPN_ACTIVE"})
        self.assertTrue(r.data["advice"])
        self.assertEqual(LocationIntegrityCheck.objects.filter(context="PRECHECK").count(), 1)

    def test_register_and_dashboard(self):
        self._upload({**CLEAN, "mock_location": True})
        admin = OfficerProfile.objects.get(role=Role.ADMIN).user
        c = APIClient(); c.force_authenticate(admin)
        r = c.get("/building-violations/api/reports/location-integrity/?decision=REJECTED")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["rows"]), 1)
        self.assertIn("MOCK_LOCATION", r.data["rows"][0][r.data["columns"].index("reasons")])
        r = c.get("/building-violations/api/integrity/checks/summary/")
        self.assertEqual(r.status_code, 200, getattr(r, "data", r.content))
        self.assertEqual(r.data["rejected"], 1)
        self.assertEqual(r.data["reasons"][0]["code"], "MOCK_LOCATION")
        r = c.get("/building-violations/api/dashboards/summary/")
        self.assertEqual(r.data["integrity_rejected_30d"], 1)
