"""Post-save hooks: compute media hash/size, parcel bbox."""
import hashlib

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import GovtLandParcel, MediaAttachment


@receiver(pre_save, sender=MediaAttachment)
def media_pre_save(sender, instance: MediaAttachment, **kwargs):
    f = instance.file
    if f and not instance.sha256:
        try:
            h = hashlib.sha256()
            for chunk in f.chunks():
                h.update(chunk)
            instance.sha256 = h.hexdigest()
            instance.size_bytes = f.size
            if hasattr(f, "seek"):
                f.seek(0)
        except Exception:
            pass
    if f and not instance.original_name:
        instance.original_name = getattr(f, "name", "")[:255]


@receiver(pre_save, sender=GovtLandParcel)
def parcel_pre_save(sender, instance: GovtLandParcel, **kwargs):
    if instance.geometry and not instance.bbox:
        from .services.geo import geojson_bbox
        try:
            instance.bbox = geojson_bbox(instance.geometry)
        except Exception:
            instance.bbox = []
