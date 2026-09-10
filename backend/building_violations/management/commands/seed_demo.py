"""Seed zones/wards/divisions, demo officers (OTP login), a few government-land parcels,
sanctioned plans and sample cases so the portal and the app can be demonstrated immediately.

Demo logins (standalone mode, OTP = BVMS_OTP_DEMO_CODE, default 123456):
  JE      9000000001   AE       9000000002   JC       9000000003
  CLERK   9000000004   XEN      9000000005   ADMIN    9000000009
  FIELD   9000000006   ADDL.COMMR 9000000007
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from building_violations.models import Division, GovtLandParcel, OfficerProfile, Role, SanctionedPlan, Ward, Zone

User = get_user_model()

WARD_ZONES = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 10: 2, 11: 2, 12: 2, 13: 2, 14: 2, 15: 2, 16: 2, 17: 2, 18: 2,
              19: 3, 20: 3, 21: 3, 22: 3, 23: 3, 24: 3, 25: 3, 26: 3, 27: 3, 28: 4, 29: 4, 30: 4, 31: 4, 32: 4, 33: 4, 34: 4, 35: 4, 36: 4}
DEMO_OFFICERS = [
    ("9000000001", Role.JE, "Junior Engineer, Zones 2-4", "Amit", "Sharma", [2, 3, 4]),
    ("9000000002", Role.AE, "Assistant Engineer, Zones 2-4", "Neha", "Verma", [2, 3, 4]),
    ("9000000003", Role.JC, "Joint Commissioner, Zones 2-4", "Vishal", "Kumar", [2, 3, 4]),
    ("9000000004", Role.JC_CLERK, "Clerk, Office of JC", "Sunil", "Yadav", [2, 3, 4]),
    ("9000000005", Role.XEN, "Executive Engineer", "Rakesh", "Singh", [2, 3, 4]),
    ("9000000006", Role.FIELD_STAFF, "Enforcement Inspector", "Deepak", "Rao", [2, 3, 4]),
    ("9000000007", Role.ADDL_COMMISSIONER, "Additional Commissioner", "Yash", "Jaluka", None),
    ("9000000009", Role.ADMIN, "Module Administrator (IT Cell)", "IT", "Admin", None),
]


class Command(BaseCommand):
    help = "Seed masters and demo data"

    def add_arguments(self, parser):
        parser.add_argument("--with-cases", action="store_true", help="also create sample cases through the workflow")

    def handle(self, *args, **opts):
        call_command("load_legal_catalogue")
        zones = {}
        for z in range(1, 5):
            zones[z], _ = Zone.objects.get_or_create(code=str(z), defaults={"name_en": f"Zone {z}", "name_hi": f"ज़ोन {z}"})
        for z in range(1, 5):
            for s in "AB":
                Division.objects.get_or_create(code=f"{z}{s}", defaults={"zone": zones[z], "name_en": f"Engineering Division {z}{s}"})
        for w, z in WARD_ZONES.items():
            Ward.objects.get_or_create(number=w, defaults={"zone": zones[z], "name_en": f"Ward {w}", "name_hi": f"वार्ड {w}",
                                                           "division": Division.objects.filter(zone=zones[z]).first()})
        jc = None
        for mobile, role, desig, first, last, zone in DEMO_OFFICERS:
            u, _ = User.objects.get_or_create(username=mobile, defaults={"first_name": first, "last_name": last})
            if role == Role.ADMIN and not u.is_staff:
                u.is_staff = u.is_superuser = True
                u.set_password("mcgadmin")
                u.save()
            p, _ = OfficerProfile.objects.get_or_create(user=u, defaults={"role": role, "designation": desig, "mobile": mobile, "email": f"{first.lower()}.{last.lower()}@mcg.gov.in"})
            for z in (zone or []):
                p.zones.add(zones[z])
            if role == Role.JC:
                jc = p
                p.delegation_order_no = "MCG/Comm/Delegation/2026/114"
                p.delegation_order_date = date(2026, 4, 1)
                p.save()
        clerk = OfficerProfile.objects.filter(role=Role.JC_CLERK).first()
        if clerk and jc:
            clerk.parent_profile = jc
            clerk.save()
        je = OfficerProfile.objects.filter(role=Role.JE).first()
        ae = OfficerProfile.objects.filter(role=Role.AE).first()
        if je and ae:
            je.reports_to = ae
            je.save()
        # a couple of government land parcels (demo polygons near Sector 14 / Sushant Lok)
        if not GovtLandParcel.objects.exists():
            GovtLandParcel.objects.create(name="Green belt, Sector 14 (demo)", agency="MCG", land_use="Green belt", village="Gurugram", khasra_no="112/2",
                                          ward=Ward.objects.get(number=19), geometry={"type": "Polygon", "coordinates": [[[77.0440, 28.4690], [77.0470, 28.4690], [77.0470, 28.4715], [77.0440, 28.4715], [77.0440, 28.4690]]]})
            GovtLandParcel.objects.create(name="Community site, Sushant Lok-1 (demo)", agency="HSVP", land_use="Community facility", village="Sukhrali", khasra_no="45",
                                          ward=Ward.objects.get(number=30), geometry={"type": "Polygon", "coordinates": [[[77.0790, 28.4610], [77.0820, 28.4610], [77.0820, 28.4635], [77.0790, 28.4635], [77.0790, 28.4610]]]})
        if not SanctionedPlan.objects.exists():
            SanctionedPlan.objects.create(plan_no="MCG/BP/2025/00412", pid="GGN012345", address="H.No. 123, Sector 14, Gurugram", ward=Ward.objects.get(number=19), zone=zones[2],
                                          latitude=28.4700, longitude=77.0450, owner_name="Ramesh Kumar", owner_mobile="9811100001", plot_area_sqm=250.84, land_use="Residential",
                                          sanctioned_on=date(2025, 6, 12), valid_till=date(2027, 6, 11), sanction_mode="self-certification", permitted_floors="S+3",
                                          permitted_ground_coverage_pct=66, permitted_far=2.0, permitted_height_m=15, setbacks={"front": 3, "rear": 3, "side": 0},
                                          architect_name="Ar. P. Mehta", architect_registration_no="CA/2010/48211", licence_authority="MCG", source="MANUAL")
        self.stdout.write(self.style.SUCCESS("Masters and demo officers seeded"))
        if opts["with_cases"]:
            self._sample_cases()

    def _sample_cases(self):
        from building_violations.models import MediaAttachment, ViolationCase
        from building_violations.services import workflow as wf
        from django.core.files.base import ContentFile
        je = OfficerProfile.objects.get(role=Role.JE).user
        ae = OfficerProfile.objects.get(role=Role.AE).user
        jc = OfficerProfile.objects.get(role=Role.JC).user
        samples = [
            dict(pid="GGN012345", pid_linked_mobile="9811100001", address_line="H.No. 123, Sector 14", locality="Sector 14", latitude=28.4700, longitude=77.0450, owner_name="Ramesh Kumar",
                 storeys="S+4", covered_area_sqm=210, description="Fourth floor being raised over sanctioned S+3; rear setback covered with rooms.", ward=Ward.objects.get(number=19),
                 measurements={"floors_permitted": "S+3", "floors_actual": "S+4", "rear_setback_required_m": 3, "rear_setback_actual_m": 0.6}),
            dict(address_line="Boundary wall and shed inside green belt opposite Sector 14 market", locality="Sector 14", latitude=28.4700, longitude=77.0455, owner_name="Unknown (Sh. Balwan)",
                 storeys="G", description="Brick boundary wall (40 m) and tin shed raised on MCG green belt; used as tyre repair shop.", ward=Ward.objects.get(number=19), alternate_mobile="9811100003"),
            dict(pid="GGN098765", pid_linked_mobile="9811100002", address_line="Plot 45, Sushant Lok Phase-1", locality="Sushant Lok-1", latitude=28.4620, longitude=77.0800, owner_name="Sunita Devi",
                 storeys="B+G+4", description="Basement converted to gym; stilt parking enclosed as shops.", ward=Ward.objects.get(number=30), construction_stage="OCCUPIED"),
        ]
        viols = [[{"code": "DV-03"}, {"code": "DV-04"}], [{"code": "GL-01"}], [{"code": "DV-06"}, {"code": "DV-07"}, {"code": "MU-01"}]]
        made = []
        for data, vv in zip(samples, viols):
            case = wf.create_case(je, data, vv)
            # placeholder geotagged "photo"
            png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            mm = MediaAttachment(case=case, kind="INSPECTION", media_type="IMAGE", latitude=data["latitude"], longitude=data["longitude"], accuracy_m=6, captured_at=timezone.now(), uploaded_by=je, caption="Front view (demo)")
            mm.file.save("demo.png", ContentFile(png), save=True)
            wf.attach_media(case, [mm.id], je)
            made.append(case)
        wf.submit_to_ae(made[0], je, remarks="Please forward for SCN")
        wf.ae_forward(made[0], ae, remarks="Violations confirmed on site", recommendation="SCN")
        wf.jc_issue_notice(made[0], jc, order_type_code="SCN_261", remarks="Issue SCN with stop-work direction")
        wf.submit_to_ae(made[1], je)
        wf.ae_forward(made[1], ae, remarks="Encroachment on green belt confirmed against GIS layer", recommendation="DEMOLITION")
        wf.submit_to_ae(made[2], je)
        self.stdout.write(self.style.SUCCESS(f"Sample cases: {', '.join(c.case_no for c in made)}"))
