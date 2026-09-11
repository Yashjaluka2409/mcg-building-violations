"""
Import government-land layers uploaded by the GIS lab: GeoJSON, KML/KMZ and zipped shapefiles.
Coordinates must be WGS84 (EPSG:4326) - QGIS: Layer > Export > Save Features As > CRS EPSG:4326.
Shapefiles are read with `pyshp` (pure Python); no GDAL needed.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET

from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from sqlalchemy.orm import Session

from app.models.building_violations import AGENCY_LABELS, GovtLandParcel, LandLayerUpload
from app.services.building_violations.geo import geojson_bbox

PROP_ALIASES = {
    "name": ["name", "NAME", "Name", "PARCEL", "parcel", "title", "LAYER"],
    "land_use": ["land_use", "LANDUSE", "landuse", "use", "USE", "LU", "category", "CATEGORY"],
    "village": ["village", "VILLAGE", "Village", "VIL_NAME", "vill"],
    "khasra_no": ["khasra", "KHASRA", "khasra_no", "KHASRA_NO", "Khasra", "survey_no", "SURVEY_NO", "KH_NO"],
    "area_sqm": ["area_sqm", "AREA_SQM", "area", "AREA", "Shape_Area", "SHAPE_AREA"],
    "agency": ["agency", "AGENCY", "owner", "OWNER", "dept", "DEPT"],
}


def _pick(props: dict, key: str, default=""):
    for k in PROP_ALIASES.get(key, [key]):
        if k in props and props[k] not in (None, ""):
            return props[k]
    return default


def _valid_wgs84(geom: dict) -> bool:
    try:
        g = shape(geom)
        minx, miny, maxx, maxy = g.bounds
        return -180 <= minx <= 180 and -180 <= maxx <= 180 and -90 <= miny <= 90 and -90 <= maxy <= 90 and not g.is_empty
    except Exception:
        return False


# ---------------------------------------------------------------- parsers -> list[(geometry, properties)]
def parse_geojson(data: bytes):
    d = json.loads(data.decode("utf-8-sig"))
    feats = d.get("features", []) if isinstance(d, dict) and d.get("type") == "FeatureCollection" else ([d] if isinstance(d, dict) and d.get("type") == "Feature" else [])
    out = []
    for f in feats:
        g = f.get("geometry")
        if g and g.get("type") in ("Polygon", "MultiPolygon"):
            out.append((g, f.get("properties") or {}))
    return out


def parse_kml(data: bytes):
    if data[:2] == b"PK":  # KMZ
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = next((n for n in z.namelist() if n.lower().endswith(".kml")), None)
            if not name:
                return []
            data = z.read(name)
    root = ET.fromstring(data)
    ns = {"k": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
    q = (lambda p: f"k:{p}") if ns else (lambda p: p)
    out = []
    for pm in root.iter(f"{{{ns['k']}}}Placemark" if ns else "Placemark"):
        props = {}
        n = pm.find(q("name"), ns)
        if n is not None and n.text:
            props["name"] = n.text.strip()
        for sd in pm.iter(f"{{{ns['k']}}}SimpleData" if ns else "SimpleData"):
            props[sd.get("name", "")] = (sd.text or "").strip()
        for dt in pm.iter(f"{{{ns['k']}}}Data" if ns else "Data"):
            v = dt.find(q("value"), ns)
            props[dt.get("name", "")] = (v.text or "").strip() if v is not None else ""
        polys = []
        for poly in pm.iter(f"{{{ns['k']}}}Polygon" if ns else "Polygon"):
            rings = []
            for ring_tag in ("outerBoundaryIs", "innerBoundaryIs"):
                for ring in poly.iter(f"{{{ns['k']}}}{ring_tag}" if ns else ring_tag):
                    c = ring.find(f".//{q('coordinates')}", ns)
                    if c is None or not c.text:
                        continue
                    pts = []
                    for tok in re.split(r"\s+", c.text.strip()):
                        parts = tok.split(",")
                        if len(parts) >= 2:
                            pts.append((float(parts[0]), float(parts[1])))
                    if len(pts) >= 4:
                        rings.append(pts)
            if rings:
                polys.append(Polygon(rings[0], rings[1:]))
        if polys:
            geom = polys[0] if len(polys) == 1 else MultiPolygon(polys)
            out.append((mapping(geom), props))
    return out


def parse_shapefile_zip(data: bytes):
    import shapefile  # pyshp
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        shp = next((n for n in names if n.lower().endswith(".shp")), None)
        if not shp:
            raise ValueError("Zip does not contain a .shp file")
        base = shp[:-4]
        dbf = next((n for n in names if n.lower() == (base + ".dbf").lower()), None)
        shx = next((n for n in names if n.lower() == (base + ".shx").lower()), None)
        prj = next((n for n in names if n.lower() == (base + ".prj").lower()), None)
        if prj:
            prj_text = z.read(prj).decode("utf-8", "ignore")
            if "PROJCS" in prj_text and "GEOGCS" in prj_text and "UTM" in prj_text.upper():
                raise ValueError("Shapefile is projected (UTM). Re-export from QGIS in EPSG:4326 (WGS84) and upload again.")
        r = shapefile.Reader(shp=io.BytesIO(z.read(shp)), dbf=io.BytesIO(z.read(dbf)) if dbf else None, shx=io.BytesIO(z.read(shx)) if shx else None)
        fields = [f[0] for f in r.fields[1:]]
        out = []
        for sr in r.iterShapeRecords():
            geo = sr.shape.__geo_interface__
            if geo.get("type") not in ("Polygon", "MultiPolygon"):
                continue
            props = dict(zip(fields, sr.record))
            out.append((geo, props))
        return out


def parse_any(filename: str, data: bytes):
    n = (filename or "").lower()
    if n.endswith((".geojson", ".json")):
        return "GEOJSON", parse_geojson(data)
    if n.endswith((".kml", ".kmz")):
        return "KML", parse_kml(data)
    if n.endswith(".zip"):
        return "SHP_ZIP", parse_shapefile_zip(data)
    # sniff
    if data[:1] in (b"{", b"["):
        return "GEOJSON", parse_geojson(data)
    if b"<kml" in data[:2000].lower() or data[:2] == b"PK":
        try:
            return "SHP_ZIP", parse_shapefile_zip(data)
        except Exception:
            return "KML", parse_kml(data)
    raise ValueError("Unsupported file type: upload .geojson, .kml/.kmz or a zipped shapefile")


# ---------------------------------------------------------------- import
def import_layer(db: Session, upload: LandLayerUpload, data: bytes, filename: str) -> LandLayerUpload:
    fmt, feats = parse_any(filename, data)
    upload.file_format = fmt
    # versioning: retire the previous active version of the same layer key
    prev = (db.query(LandLayerUpload).filter(LandLayerUpload.layer_key == upload.layer_key, LandLayerUpload.active == True, LandLayerUpload.id != upload.id)  # noqa: E712
            .order_by(LandLayerUpload.version.desc()).first())
    if prev:
        upload.version = prev.version + 1
        upload.replaces_id = prev.id
        prev.active = False
        for p in db.query(GovtLandParcel).filter(GovtLandParcel.layer_upload_id == prev.id):
            p.active = False
    n = skipped = 0
    log = []
    for geom, props in feats:
        if not _valid_wgs84(geom):
            skipped += 1
            if len(log) < 20:
                log.append(f"skipped feature {n + skipped}: not WGS84 / invalid geometry")
            continue
        agency = str(_pick(props, "agency", upload.agency)).upper()
        if agency not in AGENCY_LABELS:
            agency = upload.agency
        area = _pick(props, "area_sqm", None)
        try:
            area = float(area) if area not in (None, "") else None
        except (TypeError, ValueError):
            area = None
        try:
            with db.begin_nested():
                db.add(GovtLandParcel(
                    name=str(_pick(props, "name"))[:200], agency=agency, land_use=str(_pick(props, "land_use"))[:120], village=str(_pick(props, "village"))[:120],
                    khasra_no=str(_pick(props, "khasra_no"))[:120], area_sqm=area, geometry=geom, bbox=geojson_bbox(geom),
                    properties={k: (v if isinstance(v, (str, int, float, bool)) or v is None else str(v)) for k, v in props.items()},
                    layer_upload=upload, layer_key=upload.layer_key))
                db.flush()
            n += 1
        except Exception as exc:
            skipped += 1
            if len(log) < 20:
                log.append(f"error: {exc}")
    upload.feature_count, upload.skipped_count, upload.import_log = n, skipped, "\n".join(log)
    db.flush()
    return upload
