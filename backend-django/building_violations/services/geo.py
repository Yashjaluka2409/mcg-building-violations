"""Small geo helpers: haversine distance, point-in-parcel checks, ward detection (shapely, no GDAL)."""
from __future__ import annotations

import math

from shapely.geometry import Point, shape

from ..models import GovtLandParcel, Ward


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geojson_bbox(geom: dict) -> list:
    g = shape(geom)
    return list(g.bounds)


def parcels_containing(lat: float, lng: float, buffer_m: float = 0.0):
    """Return active parcels whose polygon contains the point (optionally within buffer_m)."""
    pt = Point(float(lng), float(lat))
    deg = buffer_m / 111_000.0
    qs = GovtLandParcel.objects.filter(active=True)
    hits = []
    for p in qs.only("id", "geometry", "bbox", "agency", "name", "khasra_no", "land_use", "village"):
        b = p.bbox or []
        if len(b) == 4 and not (b[0] - deg <= pt.x <= b[2] + deg and b[1] - deg <= pt.y <= b[3] + deg):
            continue
        try:
            g = shape(p.geometry)
        except Exception:
            continue
        if g.contains(pt) or (buffer_m and g.distance(pt) <= deg):
            hits.append(p)
    return hits


def ward_for_point(lat: float, lng: float):
    pt = Point(float(lng), float(lat))
    for w in Ward.objects.filter(active=True).exclude(boundary__isnull=True):
        try:
            if shape(w.boundary).contains(pt):
                return w
        except Exception:
            continue
    return None
