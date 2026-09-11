from django.apps import AppConfig


class BuildingViolationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "building_violations"
    verbose_name = "Building Violation Management System"

    def ready(self):
        from . import signals  # noqa: F401
