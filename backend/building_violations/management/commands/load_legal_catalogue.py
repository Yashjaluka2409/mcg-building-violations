"""Load / refresh statutes, sections, violation types and order types from shared/legal/*.json."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from building_violations.models import LegalSection, LegalStatute, OrderType, SLAConfig, ViolationType
from building_violations.services.sla import DEFAULT_ESCALATION, DEFAULT_SLA_HOURS


class Command(BaseCommand):
    help = "Load the legal catalogue (statutes, sections, violation types, order types, SLA defaults)"

    def add_arguments(self, parser):
        parser.add_argument("--dir", default=str(settings.BVMS_LEGAL_DIR))

    def handle(self, *args, **opts):
        d = Path(opts["dir"])
        sections = json.loads((d / "legal_sections.json").read_text(encoding="utf-8"))
        cat = json.loads((d / "violation_catalogue.json").read_text(encoding="utf-8"))
        for st in sections["statutes"]:
            LegalStatute.objects.update_or_create(code=st["code"], defaults={"title": st["title"], "citation": st.get("citation", ""), "jurisdiction": st.get("jurisdiction", ""), "primary": st.get("primary", True)})
        n = 0
        for s in sections["sections"]:
            LegalSection.objects.update_or_create(statute_id=s["statute"], section=s["section"], defaults={
                "heading": s["heading"], "kind": s.get("kind", "substantive"), "text": s["text"],
                "schedule_fine_inr": s.get("schedule_fine_inr"), "schedule_daily_fine_inr": s.get("schedule_daily_fine_inr"),
                "verify": s.get("verify", False), "notes": s.get("notes") or ""})
            n += 1
        for code, ot in cat["order_types"].items():
            OrderType.objects.update_or_create(code=code, defaults={
                "title_en": ot["title_en"], "title_hi": ot.get("title_hi", ""), "statute": ot["statute"], "section": ot["section"], "kind": ot["kind"],
                "min_days": ot.get("min_days", 0), "default_days": ot.get("default_days", 0), "template": ot["template"],
                "appeal_days": ot.get("appeal_days"), "appeal_to": ot.get("appeal_to") or ""})
        for i, v in enumerate(cat["violations"]):
            ViolationType.objects.update_or_create(code=v["code"], defaults={
                "category": v["category"], "title_en": v["title_en"], "title_hi": v.get("title_hi", ""), "description": v.get("description", ""),
                "contravention_of": v.get("contravention_of", ""), "legal_basis": v.get("legal_basis", []), "action_path": v["action_path"],
                "orders_available": v.get("orders_available", []), "scn_response_days_default": v.get("scn_response_days_default", 7),
                "order_compliance_days_default": v.get("order_compliance_days_default", 15), "statutory_minimum_days": v.get("statutory_minimum_days", 0),
                "severity": v.get("severity", "HIGH"), "compoundable": v.get("compoundable", "NO"), "evidence_checklist": v.get("evidence_checklist", []),
                "schedule_fine_inr": v.get("schedule_fine_inr"), "schedule_daily_fine_inr": v.get("schedule_daily_fine_inr"), "appeal": v.get("appeal") or "",
                "notes": v.get("notes") or "", "active": v.get("active", True), "sort_order": i})
        for stage, hours in DEFAULT_SLA_HOURS.items():
            SLAConfig.objects.get_or_create(stage=stage, defaults={"label": stage.replace("_", " ").title(), "hours": hours, "escalate_to_role": DEFAULT_ESCALATION.get(stage, "") or ""})
        self.stdout.write(self.style.SUCCESS(f"Loaded {LegalStatute.objects.count()} statutes, {n} sections, {ViolationType.objects.count()} violation types, {OrderType.objects.count()} order types"))
