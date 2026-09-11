"""Generate docs/06-DATABASE-SCHEMA.md from the SQLAlchemy metadata (run: python scripts/gen_schema_doc.py)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.models import building_violations as m  # noqa: E402

DOC = Path(__file__).resolve().parents[2] / "docs" / "06-DATABASE-SCHEMA.md"
NOTES = {
    ("bvms_ward", "boundary"): "GeoJSON Polygon/MultiPolygon (WGS84)",
    ("bvms_govt_land_parcel", "geometry"): "GeoJSON Polygon/MultiPolygon (WGS84); bbox cached for fast filtering",
    ("bvms_case", "id"): "UUID primary key",
    ("bvms_case", "source"): "FIELD_INSPECTION | COMPLAINT | DRONE | LEGACY_ORDER ...",
    ("bvms_case_event", "hash"): "SHA-256 over the event + prev_hash (tamper-evident chain)",
    ("bvms_media", "file"): "S3 object key or path under UPLOADS_DIR",
    ("bvms_media", "integrity_status"): "PASS | FLAGGED | REJECTED | UNVERIFIED (services/location_integrity.py)",
    ("bvms_notice", "verification_code"): "12-character code printed under the QR; public verify endpoint",
    ("bvms_notice", "is_legacy"): "order issued on paper before the system (not re-signed)",
    ("users", "id"): "UUID; JWT `sub`. Inside the platform: the unified user registry",
    ("bvms_officer_profile", "user_id"): "one profile per platform user",
    ("bvms_location_integrity", "decision"): "PASS | FLAGGED | REJECTED",
    ("bvms_workflow_setting", "value"): "typed by value_type (bool | int | str)",
}


def type_name(col) -> str:
    fks = list(col.foreign_keys)
    if fks:
        return f"FK → {fks[0].column.table.name}"
    t = col.type
    name = t.__class__.__name__
    if name == "UTCDateTime":
        return "DateTime(tz)"
    if name in ("String",) and getattr(t, "length", None):
        return f"String({t.length})"
    if name == "Numeric":
        return f"Numeric({t.precision},{t.scale})"
    return name


def main():
    models = {mapper.local_table.name: mapper.class_.__name__ for mapper in Base.registry.mappers}
    out = ["# 06 - Database Schema", "",
           "All module tables are prefixed `bvms_`; the standalone user registry is `users` (UUID primary key, like the platform's UserModel).",
           "Generated from `backend/app/models/building_violations.py` (SQLAlchemy 2.0) by `backend/scripts/gen_schema_doc.py`; the same DDL",
           "is produced by `python -m app.cli migrate` (Alembic) on PostgreSQL or SQLite. Geometry is GeoJSON in JSON columns (PostGIS optional).", ""]
    for table in Base.metadata.sorted_tables:
        out.append(f"## `{table.name}` - {models.get(table.name, 'association table')}")
        out.append("")
        out.append("| Column | Type | Null | Description |")
        out.append("|---|---|---|---|")
        for col in table.columns:
            desc = NOTES.get((table.name, col.name), "")
            if col.primary_key and not desc:
                desc = "primary key"
            elif col.unique and not desc:
                desc = "unique"
            out.append(f"| {col.name} | {type_name(col)} | {'yes' if col.nullable else 'no'} | {desc} |")
        out.append("")
    DOC.write_text("\n".join(out), encoding="utf-8")
    print("written", DOC, "-", len(Base.metadata.sorted_tables), "tables")


if __name__ == "__main__":
    main()
