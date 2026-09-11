"""Celery application used for SLA timers, notice dispatch retries and escalations.

When CELERY_BROKER_URL is empty (demo / first integration) tasks run eagerly in-process,
so nothing else has to be installed to try the module.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("mcg_bvms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["building_violations"])
