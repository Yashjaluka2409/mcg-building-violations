"""Branch referrals, admin-configurable rules / permissions / settings, re-assignment and litigation."""
from datetime import date, timedelta

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from building_violations.models import Appeal, Branch, BranchReferral, CaseStatus, MediaAttachment, OfficerProfile, Role, RolePermission, Ward, WorkflowRule, WorkflowSetting
from building_violations.services import access
from building_violations.services import workflow as wf
from building_violations.tasks import stay_expiry_sweep

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"


class AdminAndReferralTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.je = OfficerProfile.objects.get(role=Role.JE).user
        cls.ae = OfficerProfile.objects.get(role=Role.AE).user
        cls.jc = OfficerProfile.objects.get(role=Role.JC).user
        cls.admin = OfficerProfile.objects.get(role=Role.ADMIN).user
        cls.revenue = OfficerProfile.objects.get(branch__code="REVENUE").user
        cls.planning = OfficerProfile.objects.get(branch__code="PLANNING").user

    def setUp(self):
        access.invalidate()

    def _media(self, case, user, kind="INSPECTION", lat=28.4700, lng=77.0455):
        mm = MediaAttachment(case=case, kind=kind, media_type="IMAGE", latitude=lat, longitude=lng, accuracy_m=5, captured_at=timezone.now(), uploaded_by=user)
        mm.file.save("x.png", ContentFile(PNG), save=True)
        wf.attach_media(case, [mm.id], user, kind=kind)
        return mm

    def _case_at_jc(self):
        case = wf.create_case(self.je, dict(address_line="Shed on green belt", latitude=28.4700, longitude=77.0455, description="tin shed", ward=Ward.objects.get(number=19), alternate_mobile="9811100003"), [{"code": "GL-01"}])
        self._media(case, self.je)
        wf.submit_to_ae(case, self.je)
        wf.ae_forward(case, self.ae)
        return case

    # ---- referrals -----------------------------------------------------------
    def test_referral_blocks_final_order_until_branch_responds(self):
        case = self._case_at_jc()
        rev = Branch.objects.get(code="REVENUE")
        ref = wf.refer_to_branch(case, self.jc, branch=rev, query="Confirm ownership from jamabandi", hold_case=True)
        self.assertEqual(ref.status, "PENDING")
        self.assertEqual(case.status, CaseStatus.PENDING_JC)  # main workflow untouched
        scn = wf.jc_issue_notice(case, self.jc, order_type_code="SCN_408A")  # notices still allowed
        self._media(case, self.je, kind="NOTICE_DELIVERY")
        m = case.media.filter(kind="NOTICE_DELIVERY").first()
        wf.record_service(scn, self.je, mode="AFFIXATION", media_ids=[m.id])
        with self.assertRaises(wf.WorkflowError):
            wf.jc_issue_notice(case, self.jc, order_type_code="EVICTION_DEMOLITION_ORDER_408A")  # blocked by hold referral
        # planning officer cannot answer a revenue referral
        with self.assertRaises(wf.WorkflowError):
            wf.respond_to_referral(ref, self.planning, response="not mine")
        # branch officer sees the case (history) and answers
        c = APIClient(); c.force_authenticate(self.revenue)
        r = c.get(f"/building-violations/api/cases/{case.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["available_actions"], ["respond_branch"])
        self.assertGreaterEqual(len(r.json()["events"]), 5)  # full history visible
        r = c.post(f"/building-violations/api/cases/{case.id}/respond_branch/", {"referral": ref.id, "response": "Khasra 112/2 vests in MCG as per jamabandi 2023-24", "recommendation": "GOVT_LAND_CONFIRMED"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        ref.refresh_from_db()
        self.assertEqual(ref.status, "RESPONDED")
        # now the JC can pass the final order
        order = wf.jc_issue_notice(case, self.jc, order_type_code="EVICTION_DEMOLITION_ORDER_408A", remarks="Ownership confirmed by Revenue")
        self.assertTrue(order.is_final_order)
        # branch officer's list is scoped
        r = c.get("/building-violations/api/referrals/")
        self.assertEqual(r.json()["count"], 1)
        c.force_authenticate(self.planning)
        self.assertEqual(c.get("/building-violations/api/referrals/").json()["count"], 0)
        self.assertEqual(c.get(f"/building-violations/api/cases/{case.id}/").status_code, 404)  # not referred to planning

    # ---- admin: workflow rules ---------------------------------------------
    def test_admin_can_switch_off_an_action(self):
        case = wf.create_case(self.je, dict(address_line="x", description="y", ward=Ward.objects.get(number=19)), [{"code": "PL-01"}])
        self._media(case, self.je)
        c = APIClient(); c.force_authenticate(self.admin)
        r = c.put("/building-violations/api/admin/workflow-rules/", {"rules": [{"status": "DRAFT", "role": "JE", "action": "submit_to_ae", "allowed": False}], "order_reference": "MCG/IT/2026/17"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("submit_to_ae", r.json()["matrix"]["DRAFT"].get("JE", []))
        access.invalidate()
        with self.assertRaises(wf.WorkflowError):
            wf.submit_to_ae(case, self.je)
        # a JE cannot change rules
        c.force_authenticate(self.je)
        self.assertEqual(c.put("/building-violations/api/admin/workflow-rules/", {"rules": []}, format="json").status_code, 403)
        # audit log has the change with the order reference
        c.force_authenticate(self.admin)
        log = c.get("/building-violations/api/admin/audit-log/").json()
        self.assertTrue(any(x["action"] == "RULES_UPDATE" and x["order_reference"] == "MCG/IT/2026/17" for x in log))

    def test_setting_skip_ae_review(self):
        case = wf.create_case(self.je, dict(address_line="x", description="y", ward=Ward.objects.get(number=19)), [{"code": "PL-01"}])
        self._media(case, self.je)
        c = APIClient(); c.force_authenticate(self.admin)
        r = c.put("/building-violations/api/admin/settings/", {"values": {"require_ae_review": False}}, format="json")
        self.assertEqual(r.status_code, 200)
        access.invalidate()
        wf.submit_to_ae(case, self.je)
        self.assertEqual(case.status, CaseStatus.PENDING_JC)
        self.assertIsNotNone(case.assigned_jc)

    # ---- admin: permissions and overrides ----------------------------------
    def test_permission_override_grants_reports_to_je(self):
        c = APIClient(); c.force_authenticate(self.je)
        self.assertEqual(c.get("/building-violations/api/reports/case-register/").status_code, 403)
        prof = self.je.bvms_profile
        a = APIClient(); a.force_authenticate(self.admin)
        r = a.put(f"/building-violations/api/officers/{prof.id}/permissions/", {"overrides": [{"permission": "REPORTS_EXPORT", "allowed": True, "reason": "Zone MIS duty"}], "order_reference": "Endst. 1234"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        access.invalidate()
        self.assertEqual(c.get("/building-violations/api/reports/case-register/").status_code, 200)
        me = c.get("/building-violations/api/users/me/").json()
        self.assertIn("REPORTS_EXPORT", me["permissions"])
        # role-level revoke: JC loses BRANCH_REFER
        r = a.put("/building-violations/api/admin/permissions/", {"grants": [{"role": "JC", "permission": "BRANCH_REFER", "allowed": False}]}, format="json")
        self.assertEqual(r.status_code, 200)
        access.invalidate()
        case = self._case_at_jc()
        with self.assertRaises(wf.WorkflowError):
            wf.refer_to_branch(case, self.jc, branch=Branch.objects.get(code="PLANNING"), query="q")

    # ---- admin: jurisdiction & re-assignment --------------------------------
    def test_jurisdiction_change_and_bulk_reassign(self):
        case = self._case_at_jc()
        a = APIClient(); a.force_authenticate(self.admin)
        new_ae = OfficerProfile.objects.create(user=type(self.je).objects.create(username="9000000021", first_name="New", last_name="AE"), role=Role.AE, mobile="9000000021", designation="AE Zone 3")
        from building_violations.models import Zone
        r = a.patch(f"/building-violations/api/officers/{new_ae.id}/", {"zones": [Zone.objects.get(code="3").id], "wards": [Ward.objects.get(number=19).id], "order_reference": "Transfer order 77"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        r = a.post("/building-violations/api/admin/reassign-cases/", {"ward": Ward.objects.get(number=19).id, "assigned_ae": new_ae.user_id, "order_reference": "Transfer order 77"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertGreaterEqual(r.json()["reassigned"], 1)
        case.refresh_from_db()
        self.assertEqual(case.assigned_ae_id, new_ae.user_id)
        self.assertTrue(case.events.filter(action="REASSIGNED").exists())
        log = a.get("/building-violations/api/admin/audit-log/", {"search": "Transfer order 77"}).json()
        self.assertGreaterEqual(len(log), 2)

    # ---- litigation ---------------------------------------------------------
    def test_stay_requires_uploaded_order_and_resumes_clock(self):
        case = self._case_at_jc()
        scn = wf.jc_issue_notice(case, self.jc, order_type_code="SCN_408A")
        wf.record_service(scn, self.je, mode="IN_PERSON")
        order = wf.jc_issue_notice(case, self.jc, order_type_code="EVICTION_DEMOLITION_ORDER_408A", remarks="reasons")
        wf.record_service(order, self.je, mode="IN_PERSON")
        self.assertEqual(case.status, CaseStatus.ORDER_SERVED)
        with self.assertRaises(wf.WorkflowError):  # no stay order uploaded
            wf.record_appeal(case, self.jc, filed_on=date.today(), authority="HIGH_COURT", appeal_no="CWP 1234/2026", stay_granted=True)
        so = self._media(case, self.jc, kind="STAY_ORDER")
        ap = wf.record_appeal(case, self.jc, filed_on=date.today(), authority="HIGH_COURT", appeal_no="CWP 1234/2026", stay_granted=True, stay_order_media=so,
                              stay_until=date.today() + timedelta(days=2), stay_scope="STATUS_QUO", next_hearing_on=date.today() + timedelta(days=10))
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.APPEAL_STAY)
        self.assertEqual(case.litigation_status, "STAYED")
        self.assertEqual(case.litigation_authority, "HIGH_COURT")
        self.assertEqual(ap.stay_order.kind, "STAY_ORDER")
        self.assertGreaterEqual(stay_expiry_sweep(), 1)  # reminder because the stay expires within 3 days
        wf.update_appeal(ap, self.jc, status="STAY_VACATED", decided_on=date.today(), decision_summary="Stay vacated on 1st hearing", new_compliance_days=7)
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.ORDER_SERVED)
        self.assertEqual(case.litigation_status, "DECIDED")
        self.assertIsNotNone(case.compliance_due_at)
        # API: litigation register
        c = APIClient(); c.force_authenticate(self.jc)
        r = c.get("/building-violations/api/reports/litigation-register/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)
        self.assertEqual(r.json()["rows"][0][4], "Punjab & Haryana High Court")
