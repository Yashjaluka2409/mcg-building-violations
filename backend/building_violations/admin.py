from django.contrib import admin

from . import models as m


@admin.register(m.Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("code", "name_en", "active")


@admin.register(m.Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ("number", "name_en", "zone", "division", "active")
    list_filter = ("zone",)


@admin.register(m.Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("code", "zone", "active")


@admin.register(m.OfficerProfile)
class OfficerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "designation", "mobile", "active")
    list_filter = ("role", "active", "zones")
    search_fields = ("user__username", "mobile", "designation")
    filter_horizontal = ("zones", "wards", "divisions")


@admin.register(m.ViolationType)
class ViolationTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "category", "title_en", "action_path", "severity", "compoundable", "active")
    list_filter = ("category", "severity", "compoundable", "active")
    search_fields = ("code", "title_en", "title_hi")


@admin.register(m.LegalSection)
class LegalSectionAdmin(admin.ModelAdmin):
    list_display = ("statute", "section", "heading", "kind", "verify")
    list_filter = ("statute", "kind", "verify")
    search_fields = ("section", "heading", "text")


@admin.register(m.OrderType)
class OrderTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "kind", "statute", "section", "min_days", "default_days", "active")


@admin.register(m.SLAConfig)
class SLAConfigAdmin(admin.ModelAdmin):
    list_display = ("stage", "label", "hours", "escalate_to_role", "active")


@admin.register(m.GovtLandParcel)
class GovtLandParcelAdmin(admin.ModelAdmin):
    list_display = ("id", "agency", "name", "village", "khasra_no", "ward", "active")
    list_filter = ("agency", "active")
    search_fields = ("name", "khasra_no", "village")


@admin.register(m.SanctionedPlan)
class SanctionedPlanAdmin(admin.ModelAdmin):
    list_display = ("plan_no", "pid", "owner_name", "ward", "sanctioned_on", "valid_till", "licence_no", "status")
    search_fields = ("plan_no", "pid", "owner_name", "licence_no", "address")
    list_filter = ("status", "source", "zone")


class CaseViolationInline(admin.TabularInline):
    model = m.CaseViolation
    extra = 0


class NoticeInline(admin.TabularInline):
    model = m.Notice
    extra = 0
    fields = ("notice_no", "order_type", "issued_at", "served_at", "signature_status")
    readonly_fields = fields


@admin.register(m.ViolationCase)
class ViolationCaseAdmin(admin.ModelAdmin):
    list_display = ("case_no", "status", "zone", "ward", "land_type", "pid", "owner_name", "reported_by", "created_at")
    list_filter = ("status", "zone", "land_type", "priority")
    search_fields = ("case_no", "pid", "owner_name", "address_line")
    inlines = [CaseViolationInline, NoticeInline]
    readonly_fields = ("case_no", "created_at", "updated_at")


@admin.register(m.Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ("notice_no", "case", "order_type", "issued_by", "issued_at", "served_at", "signature_status")
    list_filter = ("order_type", "signature_status", "served_mode")
    search_fields = ("notice_no", "case__case_no")


@admin.register(m.CaseEvent)
class CaseEventAdmin(admin.ModelAdmin):
    list_display = ("id", "case", "at", "actor", "action", "from_status", "to_status")
    list_filter = ("action",)
    readonly_fields = [f.name for f in m.CaseEvent._meta.fields]


for mdl in (m.MediaAttachment, m.NoticeDispatch, m.CaseResponse, m.Hearing, m.Appeal, m.ExecutionRecord, m.Notification, m.LandLayerUpload, m.LegalStatute):
    admin.site.register(mdl)
