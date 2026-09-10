"""End-to-end workflow tests: JE -> AE -> JC SCN -> service -> response -> order -> service -> execution -> close,
plus statutory-minimum and geotag guards and the hash-chained audit trail."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from building_violations.models import CaseStatus, MediaAttachment, Notice, OfficerProfile, Role, ViolationCase, Ward
from building_violations.services import workflow as wf
from building_violations.services.audit import verify_chain

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class WorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.je = OfficerProfile.objects.get(role=Role.JE).user
        cls.ae = OfficerProfile.objects.get(role=Role.AE).user
        cls.jc = OfficerProfile.objects.get(role=Role.JC).user
        cls.clerk = OfficerProfile.objects.get(role=Role.JC_CLERK).user
        cls.field = OfficerProfile.objects.get(role=Role.FIELD_STAFF).user

    def _media(self, case, lat, lng, user=None, kind="INSPECTION"):
        mm = MediaAttachment(case=case, kind=kind, media_type="IMAGE", latitude=lat, longitude=lng, accuracy_m=5, captured_at=timezone.now(), uploaded_by=user or self.je)
        mm.file.save("x.png", ContentFile(PNG), save=True)
        wf.attach_media(case, [mm.id], user or self.je, kind=kind)
        return mm

    def _case(self, **over):
        data = dict(pid="GGN012345", pid_linked_mobile="9811100001", address_line="H.No. 123, Sector 14", latitude=28.4700, longitude=77.0450, owner_name="Ramesh Kumar",
                    description="Fourth floor over S+3", ward=Ward.objects.get(number=19))
        data.update(over)
        case = wf.create_case(self.je, data, [{"code": "DV-03"}, {"code": "DV-04"}])
        self._media(case, 28.4700, 77.0450)
        return case

    def test_full_private_land_flow(self):
        case = self._case()
        self.assertEqual(case.land_type, "GOVT_MCG")  # demo green-belt polygon contains the point -> auto detection
        case.land_type = "PRIVATE"; case.govt_parcel = None; case.save()
        self.assertIsNotNone(case.sanctioned_plan, "plan auto-linked by PID")
        wf.submit_to_ae(case, self.je)
        self.assertEqual(case.status, CaseStatus.PENDING_AE)
        with self.assertRaises(wf.WorkflowError):
            wf.jc_issue_notice(case, self.jc, order_type_code="SCN_261")  # wrong status
        wf.ae_forward(case, self.ae, remarks="ok", recommendation="SCN")
        self.assertEqual(case.status, CaseStatus.PENDING_JC)
        scn = wf.jc_issue_notice(case, self.jc, order_type_code="SCN_261", remarks="issue")
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.SCN_ISSUED)
        self.assertTrue(scn.pdf)
        self.assertEqual(scn.signature_status, "SIGNED")
        self.assertEqual(len(scn.document_hash), 64)
        self.assertIn("9811100001", scn.addressee_mobiles)
        self.assertEqual(scn.dispatches.count(), 1)
        # delivery proof must be geotagged at the property
        far = self._media(case, 28.60, 77.30, user=self.field, kind="NOTICE_DELIVERY")
        with self.assertRaises(wf.WorkflowError):
            wf.record_service(scn, self.field, mode="AFFIXATION", media_ids=[far.id])
        near = self._media(case, 28.4701, 77.0451, user=self.field, kind="NOTICE_DELIVERY")
        far.delete()
        wf.record_service(scn, self.field, mode="AFFIXATION", media_ids=[near.id])
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.SCN_SERVED)
        self.assertIsNotNone(case.response_due_at)
        # clerk uploads the response -> goes straight to JC
        wf.record_response(case, self.clerk, notice=scn, received_on=date.today(), received_via="JC_CLERK", summary="Owner says plan revision applied")
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.RESPONSE_PENDING_JC)
        h = wf.schedule_hearing(case, self.jc, scheduled_at=timezone.now() + timedelta(days=3), venue="JC office")
        wf.record_hearing(h, self.jc, proceedings="Heard; no sanction for 4th floor", outcome="HEARD")
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.RESPONSE_PENDING_JC)
        with self.assertRaises(wf.WorkflowError):
            wf.jc_issue_notice(case, self.jc, order_type_code="DEMOLITION_ORDER_261", days=2)  # below statutory minimum of 3 days
        order = wf.jc_issue_notice(case, self.jc, order_type_code="DEMOLITION_ORDER_261", days=15, remarks="Not regularisable: FAR exceeded")
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.ORDER_ISSUED)
        self.assertTrue(order.is_final_order)
        self.assertEqual(case.decision, "DEMOLITION")
        m2 = self._media(case, 28.4700, 77.0450, user=self.je, kind="ORDER_DELIVERY")
        wf.record_service(order, self.je, mode="IN_PERSON", media_ids=[m2.id])
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.ORDER_SERVED)
        self.assertAlmostEqual((case.compliance_due_at - case.order_served_at).days, 15)
        # simulate expiry of the 15-day clock
        case.compliance_due_at = timezone.now() - timedelta(hours=1); case.save()
        wf.mark_execution_due(case)
        self.assertEqual(case.status, CaseStatus.EXECUTION_DUE)
        ex_media = self._media(case, 28.4700, 77.0450, user=self.field, kind="EXECUTION")
        wf.record_execution(case, self.field, action="DEMOLITION", mode="CORPORATION", executed_on=timezone.now(), media_ids=[ex_media.id], police_assistance=True, cost_incurred_inr=45000)
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.EXECUTED)
        wf.verify_and_close(case, self.jc, remarks="Verified")
        self.assertEqual(case.status, CaseStatus.CLOSED)
        chain = verify_chain(case)
        self.assertTrue(chain["ok"])
        self.assertGreater(chain["events"], 12)

    def test_govt_land_408a_flow(self):
        case = wf.create_case(self.je, dict(address_line="Shed on green belt", latitude=28.4700, longitude=77.0455, description="tin shed", ward=Ward.objects.get(number=19), alternate_mobile="9811100003"), [{"code": "GL-01"}])
        self.assertEqual(case.land_type, "GOVT_MCG")
        self.assertIsNotNone(case.govt_parcel)
        self._media(case, 28.4700, 77.0455)
        wf.submit_to_ae(case, self.je)
        wf.ae_forward(case, self.ae)
        with self.assertRaises(wf.WorkflowError):
            wf.jc_issue_notice(case, self.jc, order_type_code="SCN_408A", days=3)  # statutory 7 days
        scn = wf.jc_issue_notice(case, self.jc, order_type_code="SCN_408A")
        self.assertEqual(scn.response_days, 7)
        self.assertIn("9811100003", scn.addressee_mobiles)
        with self.assertRaises(wf.WorkflowError):
            wf.jc_issue_notice(case, self.jc, order_type_code="DEMOLITION_ORDER_284")  # not available for GL-01

    def test_stop_work_and_sealing_are_interim(self):
        case = self._case()
        wf.submit_to_ae(case, self.je); wf.ae_forward(case, self.ae)
        wf.jc_issue_notice(case, self.jc, order_type_code="STOP_WORK_262")
        case.refresh_from_db()
        self.assertTrue(case.stop_work_issued)
        self.assertEqual(case.status, CaseStatus.PENDING_JC)
        wf.jc_issue_notice(case, self.jc, order_type_code="SEALING_263A", is_final_order=False)
        case.refresh_from_db()
        self.assertTrue(case.sealed)

    def test_api_roundtrip(self):
        c = APIClient()
        c.force_authenticate(self.je)
        r = c.get("/building-violations/api/masters/violation-types/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()), 30)
        r = c.get("/building-violations/api/property/pid/GGN012345/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["owner_name"], "Ramesh Kumar")
        r = c.get("/building-violations/api/gis/check-point/", {"lat": 28.47, "lng": 77.045})
        self.assertEqual(r.json()["land_type"], "GOVT_MCG")
        payload = {"pid": "GGN012345", "address_line": "H.No. 123", "latitude": 28.47, "longitude": 77.045, "description": "x", "violations": [{"code": "PL-01"}], "land_type": "PRIVATE"}
        r = c.post("/building-violations/api/cases/", payload, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        cid = r.json()["id"]
        r = c.post("/building-violations/api/cases/%s/submit/" % cid, {}, format="json")
        self.assertEqual(r.status_code, 400)  # no media yet
        with open(__file__, "rb"):
            pass
        from django.core.files.uploadedfile import SimpleUploadedFile
        up = c.post("/building-violations/api/media/", {"file": SimpleUploadedFile("a.png", PNG, content_type="image/png"), "case": cid, "kind": "INSPECTION", "latitude": "28.4700", "longitude": "77.0450"}, format="multipart")
        self.assertEqual(up.status_code, 201, up.content)
        self.assertTrue(up.json()["geotag_verified"])
        r = c.post("/building-violations/api/cases/%s/submit/" % cid, {}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["status"], "PENDING_AE")
        c.force_authenticate(self.ae)
        self.assertEqual(c.post("/building-violations/api/cases/%s/ae_forward/" % cid, {"remarks": "go"}, format="json").status_code, 200)
        c.force_authenticate(self.jc)
        r = c.post("/building-violations/api/cases/%s/issue_notice/" % cid, {"order_type": "SCN_261", "days": 7}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        nid = r.json()["notice"]["id"]
        code = r.json()["notice"]["verification_code"]
        pdf = c.get(f"/building-violations/api/notices/{nid}/pdf/")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        pub = APIClient().get(f"/building-violations/public/verify/{code}/")
        self.assertTrue(pub.json()["valid"])
        r = c.get("/building-violations/api/dashboards/summary/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.json()["scn_issued"], 1)
        r = c.get("/building-violations/api/reports/case-register/", {"export": "csv"})
        self.assertEqual(r.status_code, 200)
        c.force_authenticate(self.clerk)
        r = c.post("/building-violations/api/cases/%s/issue_notice/" % cid, {"order_type": "SCN_261"}, format="json")
        self.assertEqual(r.status_code, 403)  # clerk cannot issue
