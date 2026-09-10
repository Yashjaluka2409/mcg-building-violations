import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, RotateCcw, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { property } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import MapView from "@/components/MapView";
import { Alert, Card, Field } from "@/components/ui";
import { fmtDate, fmtDateTime } from "@/utils/format";
import { useAuth } from "@/store/auth";

const AGENCIES = ["MCG", "HSVP", "GMDA", "STATE_GOVT", "PWD", "IRRIGATION", "FOREST", "PANCHAYAT", "RAILWAYS", "NHAI", "DEFENCE", "OTHER"];

/** Government-land database maintained by the GIS lab: versioned layers (GeoJSON / KML / zipped
 *  shapefile, WGS84). Polygons show live case status; clicking a parcel lists its cases. */
export default function GovtLandPage() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const user = useAuth((s) => s.user);
  const canManage = (user?.permissions || []).includes("LAND_LAYERS_MANAGE");
  const [f, setF] = useState<Record<string, any>>({ agency: "MCG" });
  const [msg, setMsg] = useState<{ kind: "info" | "error" | "success"; text: string } | null>(null);
  const land = useQuery({ queryKey: ["govt-land"], queryFn: () => property.govtLandGeoJson() });
  const layers = useQuery({ queryKey: ["land-layers"], queryFn: property.landLayers, enabled: true });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["govt-land"] }); qc.invalidateQueries({ queryKey: ["land-layers"] }); };
  const up = useMutation({ mutationFn: () => { const fd = new FormData(); for (const k of ["name", "layer_key", "agency", "source", "survey_date", "remarks", "order_reference"]) if (f[k]) fd.append(k, f[k]); fd.append("source_file", f.file); return property.uploadLandLayer(fd); }, onSuccess: (r) => { setMsg({ kind: r.skipped_count ? "info" : "success", text: `Layer "${r.name}" v${r.version} (${r.file_format}) loaded: ${r.feature_count} parcels${r.skipped_count ? `, ${r.skipped_count} skipped - ${r.import_log.split("\n")[0]}` : ""}` }); setF({ agency: f.agency }); refresh(); }, onError: (e) => setMsg({ kind: "error", text: errorMessage(e) }) });
  const retire = useMutation({ mutationFn: (id: number) => property.retireLayer(id), onSuccess: refresh });
  const reactivate = useMutation({ mutationFn: (id: number) => property.reactivateLayer(id), onSuccess: refresh });
  const counts: Record<string, number> = {}; let openCases = 0;
  for (const ft of land.data?.features || []) { counts[ft.properties.agency] = (counts[ft.properties.agency] || 0) + 1; openCases += ft.properties.open_case_count || 0; }
  const slug = (v: string) => v.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return (
    <div className="space-y-4">
      <div><h1 className="page-title">Government land database</h1><p className="page-sub">Layers uploaded by the GIS lab (GeoJSON / KML / KMZ / zipped shapefile, EPSG:4326). Every inspection point and geotagged photo is tested against these parcels; parcels with open encroachment cases are shown in red - click one for its case history.</p></div>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="grid lg:grid-cols-3 gap-4">
        <Card title={<span className="flex items-center gap-2"><Layers className="h-4 w-4" />Map · {land.data?.features?.length ?? 0} active parcels · {openCases} open case(s) on government land</span>} className="lg:col-span-2"><MapView govtLand={land.data} fit legend height="560px" onOpenCase={(id) => nav(`/cases/${id}`)} /><div className="flex flex-wrap gap-2 mt-2 text-xs">{Object.entries(counts).map(([a, n]) => <span key={a} className="badge bg-gray-100">{a}: {n}</span>)}</div></Card>
        <div className="space-y-4">
          {canManage && <Card title="Upload / update a layer"><div className="space-y-2">
            <Field label="Layer name" required><input className="input" value={f.name || ""} onChange={(e) => setF({ ...f, name: e.target.value, layer_key: f.layer_key_manual ? f.layer_key : slug(e.target.value) })} placeholder="e.g. MCG green belts - Zone 2" /></Field>
            <Field label="Layer key" hint="Re-uploading with the same key creates a new version and retires the old parcels" required><input className="input font-mono" value={f.layer_key || ""} onChange={(e) => setF({ ...f, layer_key: slug(e.target.value), layer_key_manual: true })} /></Field>
            <div className="grid grid-cols-2 gap-2"><Field label="Owning agency (default)"><select className="input" value={f.agency} onChange={(e) => setF({ ...f, agency: e.target.value })}>{AGENCIES.map((a) => <option key={a}>{a}</option>)}</select></Field><Field label="Survey / record date"><input type="date" className="input" value={f.survey_date || ""} onChange={(e) => setF({ ...f, survey_date: e.target.value })} /></Field></div>
            <Field label="Source"><input className="input" value={f.source || ""} onChange={(e) => setF({ ...f, source: e.target.value })} placeholder="Revenue record / survey / drone / DTP layout" /></Field>
            <Field label="File (.geojson / .kml / .kmz / .zip shapefile)" required><input type="file" accept=".geojson,.json,.kml,.kmz,.zip" className="input" onChange={(e) => setF({ ...f, file: e.target.files?.[0] || null })} /></Field>
            <Field label="Order / memo reference"><input className="input" value={f.order_reference || ""} onChange={(e) => setF({ ...f, order_reference: e.target.value })} /></Field>
            <button className="btn-primary w-full" disabled={!f.file || !f.name || !f.layer_key || up.isPending} onClick={() => up.mutate()}><Upload className="h-4 w-4" />{up.isPending ? "Importing…" : "Upload layer"}</button>
            <div className="text-[11px] text-light-text-muted">Attributes read if present: name, land_use, village, khasra, area_sqm, agency. Projected shapefiles (UTM) are rejected - export in EPSG:4326 from QGIS (Layer → Export → Save Features As → CRS EPSG:4326).</div>
          </div></Card>}
          <Card title="Layer versions"><div className="space-y-2 max-h-[420px] overflow-y-auto">{(layers.data?.results || []).length ? layers.data!.results.map((l) => <div key={l.id} className={`rounded-lg border p-2 text-xs ${l.active ? "border-success-100 bg-success-50/40" : "border-light-border opacity-70"}`}><div className="flex items-center gap-2"><b>{l.name}</b><span className="badge bg-gray-100">v{l.version}</span><span className="badge bg-primary-50 text-primary-700">{l.agency}</span><span className="badge bg-gray-100">{l.file_format}</span>{!l.active && <span className="badge bg-gray-200">retired</span>}</div><div className="text-light-text-muted">{l.layer_key} · {l.feature_count} parcels ({l.active_parcels} active){l.skipped_count ? ` · ${l.skipped_count} skipped` : ""} · {l.source || "-"}{l.survey_date ? ` · ${fmtDate(l.survey_date)}` : ""}</div><div className="text-light-text-muted">{fmtDateTime(l.created_at)} · {l.uploaded_by?.name}</div>{canManage && <div className="flex gap-2 mt-1">{l.active ? <button className="btn-ghost px-2 py-0.5 text-xs" onClick={() => confirm("Retire this layer version? Its parcels stop being used for detection.") && retire.mutate(l.id)}><Trash2 className="h-3 w-3" />Retire</button> : <button className="btn-ghost px-2 py-0.5 text-xs" onClick={() => reactivate.mutate(l.id)}><RotateCcw className="h-3 w-3" />Reactivate</button>}</div>}</div>) : <div className="text-sm text-light-text-muted">No layers uploaded yet.</div>}</div></Card>
        </div>
      </div>
    </div>
  );
}
