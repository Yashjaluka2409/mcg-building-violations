"""Orders issued before the system: single import at each stage, bulk register import, historical status updates,
permission, duplicate protection, audit chain, register and dashboard."""
import io
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from building_violations.models import Appeal, CaseStatus, ExecutionRecord, LegacyOrderBatch, Notice, OfficerProfile, Role, ViolationCase, ViolationType
from building_violations.services.audit import verify_chain

BASE = "/building-violations/api"


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class LegacyOrderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.jc = OfficerProfile.objects.filter(role=Role.JC).first().user
        cls.je = OfficerProfile.objects.filter(role=Role.JE).first().user
        cls.admin = OfficerProfile.objects.filter(role=Role.ADMIN).first().user

    def setUp(self):
        self.c = APIClient(); self.c.force_authenticate(self.jc)

    def _order(self, **kw):
        d = {"order_no": "MCG/JC-2/DEMO/2023/0412", "order_date": "2023-08-14", "order_type": "DEMOLITION_ORDER_261", "issued_by_name": "R. K. Sharma",
             "issued_by_designation": "Joint Commissioner, Zone 2", "pid": "GGN012345", "address_line": "H.No. 123, Sector 14", "ward_number": 19,
             "owner_name": "Ramesh Kumar", "pid_linked_mobile": "9811100001", "compliance_days": 15, "legacy_reference": "Demolition order register 2023-24 p.61",
             "violations": [{"code": ViolationType.objects.first().code, "remarks": "third floor"}]}
        d.update(kw)
        return d

    # ---- single imports -------------------------------------------------------------
    def test_import_order_issued_only(self):
        r = self.c.post(f"{BASE}/legacy-orders/", self._order(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        case = ViolationCase.objects.get(id=r.data["id"])
        self.assertEqual((case.source, case.status, case.decision), ("LEGACY_ORDER", CaseStatus.ORDER_ISSUED, "DEMOLITION"))
        n = case.final_order
        self.assertTrue(n.is_legacy and n.is_final_order)
        self.assertEqual(n.notice_no, "MCG/JC-2/DEMO/2023/0412")
        self.assertEqual(n.issued_at.date(), date(2023, 8, 14))
        self.assertIn("Joint Commissioner", n.signer_name)
        self.assertEqual(case.order_issued_at.date(), date(2023, 8, 14))
        self.assertEqual(case.compliance_due_at.date(), date(2023, 8, 29))          # order date + 15 days (not served yet)
        self.assertEqual([e.action for e in case.events.order_by("at", "id")], ["LEGACY_IMPORT", "LEGACY_STATUS"])
        self.assertTrue(verify_chain(case)["ok"] if isinstance(verify_chain(case), dict) else verify_chain(case))
        self.assertEqual(r.data["legacy_reference"], "Demolition order register 2023-24 p.61")
        self.assertIn("record_appeal", r.data["available_actions"])               # normal workflow continues (JC actions)
        self.assertEqual(Notice.objects.get(notice_no="MCG/JC-2/DEMO/2023/0412").case_id, case.id)

    def test_import_served_order_gets_execution_due_when_period_over(self):
        r = self.c.post(f"{BASE}/legacy-orders/", self._order(order_no="MCG/JC-2/DEMO/2023/0413", served_on="2023-08-20", served_mode="AFFIXATION"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        case = ViolationCase.objects.get(id=r.data["id"])
        self.assertEqual(case.status, CaseStatus.EXECUTION_DUE)
        self.assertEqual(case.order_served_at.date(), date(2023, 8, 20))
        self.assertEqual(case.compliance_due_at.date(), date(2023, 9, 4))          # served + 15 days
        self.assertEqual(case.final_order.served_mode, "AFFIXATION")

    def test_import_executed_order(self):
        r = self.c.post(f"{BASE}/legacy-orders/", self._order(order_no="MCG/JC-2/DEMO/2022/0099", order_date="2022-03-01", served_on="2022-03-05",
                                                          executed_on="2022-04-02", execution_action="DEMOLITION", cost_incurred_inr="45000"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        case = ViolationCase.objects.get(id=r.data["id"])
        self.assertEqual(case.status, CaseStatus.EXECUTED)
        ex = ExecutionRecord.objects.get(case=case)
        self.assertEqual((ex.action, ex.mode, ex.executed_on.date()), ("DEMOLITION", "CORPORATION", date(2022, 4, 2)))
        self.assertEqual(str(case.demolition_cost_inr), "45000.00")
        self.assertIn("close", r.data["available_actions"])

    def test_import_stayed_order(self):
        r = self.c.post(f"{BASE}/legacy-orders/", self._order(order_no="MCG/JC-2/DEMO/2024/0010", order_date="2024-01-10", served_on="2024-01-12",
                                                          appeal_authority="HIGH_COURT", appeal_no="CWP 1234/2024", appeal_filed_on="2024-01-20",
                                                          stay_granted=True, stay_order_date="2024-01-25"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        case = ViolationCase.objects.get(id=r.data["id"])
        self.assertEqual((case.status, case.litigation_status, case.litigation_authority), (CaseStatus.APPEAL_STAY, "STAYED", "HIGH_COURT"))
        self.assertEqual(Appeal.objects.get(case=case).status, Appeal.Status.STAYED)

    def test_import_closed_order_and_explicit_status(self):
        r = self.c.post(f"{BASE}/legacy-orders/", self._order(order_no="MCG/JC-2/DEMO/2021/0005", order_date="2021-06-01", current_status="REGULARISED",
                                                          closed_on="2021-09-01", closure_reason="Compounded under s.256"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        case = ViolationCase.objects.get(id=r.data["id"])
        self.assertEqual(case.status, CaseStatus.REGULARISED)
        self.assertEqual(case.closed_at.date(), date(2021, 9, 1))

    # ---- guards ---------------------------------------------------------------------
    def test_duplicate_order_number_rejected(self):
        self.assertEqual(self.c.post(f"{BASE}/legacy-orders/", self._order(), format="json").status_code, 201)
        r = self.c.post(f"{BASE}/legacy-orders/", self._order(), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("already on record", r.data["detail"])

    def test_je_cannot_import(self):
        c = APIClient(); c.force_authenticate(self.je)
        self.assertEqual(c.post(f"{BASE}/legacy-orders/", self._order(), format="json").status_code, 403)

    def test_requires_order_no_date_and_property(self):
        r = self.c.post(f"{BASE}/legacy-orders/", {**self._order(), "pid": "", "address_line": ""}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.c.post(f"{BASE}/legacy-orders/", {**self._order(), "order_type": "SCN_261"}, format="json")
        self.assertEqual(r.status_code, 400)

    # ---- status updates from the paper file -----------------------------------------
    def test_update_status_from_paper_file(self):
        case_id = self.c.post(f"{BASE}/legacy-orders/", self._order(), format="json").data["id"]
        r = self.c.post(f"{BASE}/legacy-orders/{case_id}/status/", {"status": "ORDER_SERVED", "on_date": "2023-08-21", "served_mode": "IN_PERSON", "order_reference": "File 12/2023"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["status"], "ORDER_SERVED")
        case = ViolationCase.objects.get(id=case_id)
        self.assertEqual(case.compliance_due_at.date(), date(2023, 9, 5))          # recomputed from service
        r = self.c.post(f"{BASE}/legacy-orders/{case_id}/status/", {"status": "APPEAL_STAY", "on_date": "2023-09-01", "appeal_authority": "DIVISIONAL_COMMISSIONER", "stay_until": "2024-03-31"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(ViolationCase.objects.get(id=case_id).litigation_status, "STAYED")
        r = self.c.post(f"{BASE}/legacy-orders/{case_id}/status/", {"status": "ORDER_SERVED", "on_date": "2024-04-02", "remarks": "Stay vacated by order dated 1.4.2024"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        case.refresh_from_db()
        self.assertEqual((case.status, case.litigation_status), ("ORDER_SERVED", "DECIDED"))
        r = self.c.post(f"{BASE}/legacy-orders/{case_id}/status/", {"status": "EXECUTED", "on_date": "2024-05-10", "execution_action": "PARTIAL_DEMOLITION"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        case.refresh_from_db()
        self.assertEqual((case.status, case.executed_at.date()), ("EXECUTED", date(2024, 5, 10)))
        actions = [e.action for e in case.events.order_by("at", "id")]
        self.assertEqual(actions.count("LEGACY_STATUS"), 5)
        self.assertIn("File 12/2023", case.events.filter(action="LEGACY_STATUS").order_by("at", "id")[1].remarks)
        # a normal (non-legacy) case cannot be short-cut this way
        normal = ViolationCase.objects.exclude(source="LEGACY_ORDER").first()
        if normal:
            self.assertEqual(self.c.post(f"{BASE}/legacy-orders/{normal.id}/status/", {"status": "EXECUTED"}, format="json").status_code, 404)

    # ---- bulk register -------------------------------------------------------------
    def test_bulk_import_from_register(self):
        tmpl = self.c.get(f"{BASE}/legacy-orders/template/")
        self.assertEqual(tmpl.status_code, 200)
        header = tmpl.content.decode().splitlines()[0]
        rows = [header,
                "MCG/JC-3/DEMO/2022/0001,2022-02-01,DEMOLITION_ORDER_261,JC Zone 3,GGN098765,Plot 45 Sushant Lok,Sushant Lok,,,Suresh,9811100002,,Illegal 4th floor,15,2022-02-05,AFFIXATION,,,,,,,,,,,,Register 2022 p.3,",
                "MCG/JC-3/SEAL/2022/0002,2022-05-01,SEALING_263A,JC Zone 3,,Shop 4 Sadar Bazar,Sadar Bazar,,,Mahesh,,,Misuse,0,2022-05-02,IN_PERSON,,2022-05-03,SEALING,CORPORATION,,,,,,,Register 2022 p.9,",
                "MCG/JC-3/DEMO/2022/0003,not-a-date,DEMOLITION_ORDER_261,JC Zone 3,,Some address,,,,,,,,,,,,,,,,,,,,,,"]
        f = SimpleUploadedFile("register.csv", "\n".join(rows).encode(), content_type="text/csv")
        r = self.c.post(f"{BASE}/legacy-orders/bulk/", {"file": f, "title": "Zone 3 register 2022", "order_reference": "Commissioner's order 44/2026"}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.data["total_rows"], r.data["imported"], len(r.data["errors"])), (3, 2, 1))
        self.assertEqual(r.data["errors"][0]["row"], 4)
        batch = LegacyOrderBatch.objects.get(id=r.data["id"])
        self.assertEqual(batch.cases.count(), 2)
        sealed = ViolationCase.objects.get(final_order__notice_no="MCG/JC-3/SEAL/2022/0002")
        self.assertEqual((sealed.status, sealed.sealed), (CaseStatus.EXECUTED, True))
        self.assertEqual(Notice.objects.filter(is_legacy=True).count(), 2)
        # list, summary, register, dashboard
        r = self.c.get(f"{BASE}/legacy-orders/?status=EXECUTION_DUE,EXECUTED")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["results"]), 2)
        r = self.c.get(f"{BASE}/legacy-orders/summary/")
        self.assertEqual(r.data["total"], 2)
        c = APIClient(); c.force_authenticate(self.admin)
        r = c.get(f"{BASE}/reports/legacy-orders/")
        self.assertEqual(len(r.data["rows"]), 2)
        r = c.get(f"{BASE}/dashboards/summary/")
        self.assertEqual(r.data["legacy_orders_total"], 2)
        r = self.c.get(f"{BASE}/legacy-orders/batches/")
        self.assertEqual(r.data[0]["imported"], 2)
