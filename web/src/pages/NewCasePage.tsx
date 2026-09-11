import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, LocateFixed, MapPin, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { cases, masters, plans, property, tasks as tasksApi } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import type { Media, ViolationType } from "@/api/types";
import MapView from "@/components/MapView";
import MediaGallery from "@/components/MediaGallery";
import Uploader from "@/components/Uploader";
import { Alert, Card, Field, SeverityBadge } from "@/components/ui";

/** New inspection (JE). Mirrors the mobile flow: PID → property auto-fill → location → land check →
 *  violations → measurements → evidence → submit to AE. */
export default function NewCasePage() {
  const nav = useNavigate();
  const { id } = useParams();
  const vtypes = useQuery({ queryKey: ["vtypes"], queryFn: masters.violationTypes });
  const zones = useQuery({ queryKey: ["zones"], queryFn: masters.zones });
  const wards = useQuery({ queryKey: ["wards-all"], queryFn: () => masters.wards() });
  const existing = useQuery({ queryKey: ["case", id], queryFn: () => cases.get(id!), enabled: !!id });
  const [sp] = useSearchParams();
  const taskId = sp.get("task") ? Number(sp.get("task")) : null;
  const task = useQuery({ queryKey: ["task", taskId], queryFn: () => tasksApi.get(taskId!), enabled: !!taskId });
  const [f, setF] = useState<Record<string, any>>({ source: "FIELD_INSPECTION", priority: "NORMAL", construction_stage: "UNDER_CONSTRUCTION", land_type: "UNKNOWN", measurements: {} });
  const [sel, setSel] = useState<Record<string, { remarks: string; details: Record<string, string> }>>({});
  const [media, setMedia] = useState<Media[]>([]);
  const [pidInfo, setPidInfo] = useState<any>(null);
  const [landCheck, setLandCheck] = useState<any>(null);
  const [planMatch, setPlanMatch] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => { if (existing.data) { const c = existing.data; setF({ ...c, ward: c.ward, zone: c.zone }); setSel(Object.fromEntries(c.violations.map((v) => [v.code, { remarks: v.remarks, details: v.details as any }]))); setMedia(c.media); } }, [existing.data]);
  useEffect(() => { if (task.data && !id) { const t = task.data; setF((s) => ({ ...s, pid: t.pid || s.pid, address_line: t.address || s.address_line, owner_name: t.owner_name || s.owner_name, pid_linked_mobile: t.owner_mobile || s.pid_linked_mobile, latitude: t.latitude ?? s.latitude, longitude: t.longitude ?? s.longitude, ward: t.ward ?? s.ward, zone: t.zone ?? s.zone, source: t.category === "COMPLAINT" ? "COMPLAINT" : t.category === "DRONE_FLAG" ? "DRONE" : t.category === "COURT_DIRECTION" ? "COURT" : "FIELD_INSPECTION", description: s.description || `[Planned inspection #${t.id} - ${t.category_display}] ${t.instructions}\n\nObservations: ` })); if (t.latitude && t.longitude) check(Number(t.latitude), Number(t.longitude)); } }, [task.data, id]);
  const set = (k: string, v: any) => setF((s) => ({ ...s, [k]: v }));
  const lookup = useMutation({ mutationFn: () => property.lookupPid(f.pid), onSuccess: async (d) => { setPidInfo(d); setF((s) => ({ ...s, owner_name: d.owner_name || s.owner_name, pid_linked_mobile: d.mobile || s.pid_linked_mobile, address_line: d.address || s.address_line, locality: d.colony || s.locality, sector: d.sector || s.sector, latitude: d.latitude ?? s.latitude, longitude: d.longitude ?? s.longitude, pid_snapshot: d.raw || d, ward: wards.data?.find((w) => String(w.number) === String(d.ward_no))?.id ?? s.ward })); try { setPlanMatch(await plans.byPid(f.pid)); } catch { setPlanMatch([]); } if (d.latitude && d.longitude) check(d.latitude, d.longitude); }, onError: (e) => setErr(errorMessage(e)) });
  const check = async (lat: number, lng: number) => { try { const r = await property.checkPoint(lat, lng); setLandCheck(r); setF((s) => ({ ...s, latitude: lat, longitude: lng, land_type: r.land_type, ward: r.ward?.id ?? s.ward })); } catch { /* ignore */ } };
  const locate = () => navigator.geolocation?.getCurrentPosition((p) => { set("location_accuracy_m", Math.round(p.coords.accuracy)); check(p.coords.latitude, p.coords.longitude); }, () => setErr("Could not read device location"), { enableHighAccuracy: true, timeout: 10000 });
  const save = useMutation({
    mutationFn: async (submit: boolean) => {
      const payload: any = { ...f, violations: Object.entries(sel).map(([code, v], i) => ({ code, remarks: v.remarks, details: v.details, is_primary: i === 0 })), media_ids: media.map((m) => m.id), submit };
      if (taskId) {
        payload.task = taskId;
        const pos = await new Promise<GeolocationPosition | null>((res) => navigator.geolocation ? navigator.geolocation.getCurrentPosition(res, () => res(null), { enableHighAccuracy: true, timeout: 10000 }) : res(null));
        if (!pos) throw new Error("Device location is required to record a planned inspection (allow location access or use the mobile app)");
        payload.inspector_latitude = pos.coords.latitude.toFixed(7); payload.inspector_longitude = pos.coords.longitude.toFixed(7);
        payload.location_integrity = { source: "web", platform: "web", native_module: false, user_agent: navigator.userAgent, fix_at: new Date(pos.timestamp).toISOString() };
      }
      if (!payload.latitude) delete payload.latitude; if (!payload.longitude) delete payload.longitude;
      for (const k of Object.keys(payload)) if (payload[k] === "" || payload[k] === null) delete payload[k];
      if (id) { const c = await cases.patch(id, payload); if (submit) await cases.action(id, "submit"); return c; }
      return cases.create(payload);
    },
    onSuccess: (c) => nav(`/cases/${c.id}`), onError: (e: any) => setErr(e?.response ? errorMessage(e) : String(e?.message || e)),
  });
  const filtered = useMemo(() => (vtypes.data || []).filter((v: ViolationType) => (!cat || v.category === cat) && (!q || `${v.code} ${v.title_en} ${v.title_hi}`.toLowerCase().includes(q.toLowerCase()))), [vtypes.data, cat, q]);
  const cats = useMemo(() => Array.from(new Set((vtypes.data || []).map((v) => v.category))), [vtypes.data]);
  const toggle = (code: string) => setSel((s) => { const n = { ...s }; if (n[code]) delete n[code]; else n[code] = { remarks: "", details: {} }; return n; });
  const wardOpts = wards.data?.filter((w) => !f.zone || w.zone === Number(f.zone)) || [];
  return (
    <div className="space-y-4 max-w-6xl">
      <div><h1 className="page-title">{id ? "Edit inspection" : "New inspection"}</h1><p className="page-sub">Record a building violation for review by the Assistant Engineer</p></div>
      {err && <Alert kind="error">{err}</Alert>}
      {task.data && <Alert kind="info"><b>Planned inspection #{task.data.id}</b> pushed by {task.data.created_by?.name} · {task.data.category_display} · due {task.data.due_at?.slice(0, 10)}. Instructions: {task.data.instructions}. Your device location will be checked against the property (within {task.data.geofence_m} m) when you save.</Alert>}
      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="1. Property">
          <div className="space-y-3">
            <Field label="Property ID (PID)" hint="DULB property ID; leave blank if not available and enter the address">
              <div className="flex gap-2"><input className="input font-mono" value={f.pid || ""} onChange={(e) => set("pid", e.target.value.toUpperCase())} placeholder="e.g. GGN012345" /><button className="btn-accent" disabled={!f.pid || lookup.isPending} onClick={() => lookup.mutate()}><Search className="h-4 w-4" />Fetch</button></div>
            </Field>
            {pidInfo && <div className="rounded-lg bg-accent-50 border border-accent-100 p-3 text-sm"><div className="font-semibold flex items-center gap-1"><CheckCircle2 className="h-4 w-4 text-accent-600" />PID record found</div><div>{pidInfo.owner_name} · {pidInfo.mobile} · {pidInfo.property_type} {pidInfo.sub_type}</div><div className="text-xs text-light-text-muted">{pidInfo.address} · Ward {pidInfo.ward_no} · Plot {pidInfo.plot_area_sqyd} sq yd · {pidInfo.floors}</div></div>}
            {planMatch.length > 0 && <div className="rounded-lg bg-success-50 border border-success-100 p-3 text-sm"><div className="font-semibold">Sanctioned plan on record</div>{planMatch.map((p) => <div key={p.id} className="text-xs">{p.plan_no} · {p.sanctioned_on} · {p.permitted_floors} · coverage {p.permitted_ground_coverage_pct}% · FAR {p.permitted_far} · height {p.permitted_height_m} m {p.licence_no && `· licence ${p.licence_no}`}</div>)}</div>}
            <Field label="Address" required><textarea className="input" rows={2} value={f.address_line || ""} onChange={(e) => set("address_line", e.target.value)} /></Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Locality / colony"><input className="input" value={f.locality || ""} onChange={(e) => set("locality", e.target.value)} /></Field>
              <Field label="Sector"><input className="input" value={f.sector || ""} onChange={(e) => set("sector", e.target.value)} /></Field>
              <Field label="Zone"><select className="input" value={f.zone || ""} onChange={(e) => set("zone", e.target.value ? Number(e.target.value) : null)}><option value="">-</option>{zones.data?.map((z) => <option key={z.id} value={z.id}>Zone {z.code}</option>)}</select></Field>
              <Field label="Ward"><select className="input" value={f.ward || ""} onChange={(e) => set("ward", e.target.value ? Number(e.target.value) : null)}><option value="">-</option>{wardOpts.map((w) => <option key={w.id} value={w.id}>Ward {w.number}</option>)}</select></Field>
              <Field label="Owner name"><input className="input" value={f.owner_name || ""} onChange={(e) => set("owner_name", e.target.value)} /></Field>
              <Field label="Father's / husband's name"><input className="input" value={f.owner_father_name || ""} onChange={(e) => set("owner_father_name", e.target.value)} /></Field>
              <Field label="Mobile linked to PID"><input className="input" value={f.pid_linked_mobile || ""} onChange={(e) => set("pid_linked_mobile", e.target.value)} /></Field>
              <Field label="Alternate mobile (for notice)"><input className="input" value={f.alternate_mobile || ""} onChange={(e) => set("alternate_mobile", e.target.value)} /></Field>
              <Field label="Occupier / builder"><input className="input" value={f.builder_name || ""} onChange={(e) => set("builder_name", e.target.value)} /></Field>
              <Field label="Person present on site"><input className="input" value={f.person_on_site || ""} onChange={(e) => set("person_on_site", e.target.value)} /></Field>
            </div>
          </div>
        </Card>
        <Card title="2. Location & land status" actions={<button className="btn-outline text-xs" onClick={locate}><LocateFixed className="h-4 w-4" />Use my location</button>}>
          <MapView height="260px" marker={f.latitude && f.longitude ? [Number(f.latitude), Number(f.longitude)] : null} onClick={(lat, lng) => check(lat, lng)} govtLand={landCheck?.parcels?.length ? { type: "FeatureCollection", features: landCheck.parcels.map((p: any) => ({ type: "Feature", geometry: p.geometry, properties: p })) } : undefined} />
          <div className="grid grid-cols-3 gap-2 mt-3">
            <Field label="Latitude"><input className="input" value={f.latitude ?? ""} onChange={(e) => set("latitude", e.target.value)} /></Field>
            <Field label="Longitude"><input className="input" value={f.longitude ?? ""} onChange={(e) => set("longitude", e.target.value)} /></Field>
            <Field label="Land type"><select className="input" value={f.land_type} onChange={(e) => set("land_type", e.target.value)}>{["UNKNOWN", "PRIVATE", "GOVT_MCG", "GOVT_STATE"].map((l) => <option key={l} value={l}>{l}</option>)}</select></Field>
          </div>
          {landCheck && <div className={`mt-2 rounded-lg p-3 text-sm border ${landCheck.parcels.length ? "bg-danger-50 border-danger-100 text-danger-700" : "bg-gray-50 border-light-border"}`}><MapPin className="h-4 w-4 inline mr-1" />{landCheck.parcels.length ? <>Point falls inside <b>{landCheck.parcels[0].agency}</b> land: {landCheck.parcels[0].name || landCheck.parcels[0].khasra_no} ({landCheck.parcels[0].land_use || "govt land"}) - select a Government-land violation (GL-xx).</> : "Not inside any mapped government-land parcel."}{landCheck.ward && <span> · Ward {landCheck.ward.number}</span>}</div>}
          <div className="grid grid-cols-2 gap-2 mt-3">
            <Field label="Construction stage"><select className="input" value={f.construction_stage} onChange={(e) => set("construction_stage", e.target.value)}>{["PLINTH", "UNDER_CONSTRUCTION", "COMPLETED", "OCCUPIED"].map((s) => <option key={s}>{s}</option>)}</select></Field>
            <Field label="Priority"><select className="input" value={f.priority} onChange={(e) => set("priority", e.target.value)}>{["LOW", "NORMAL", "HIGH", "URGENT"].map((s) => <option key={s}>{s}</option>)}</select></Field>
            <Field label="Plot area (sq m)"><input className="input" value={f.plot_area_sqm ?? ""} onChange={(e) => set("plot_area_sqm", e.target.value)} /></Field>
            <Field label="Covered area (sq m)"><input className="input" value={f.covered_area_sqm ?? ""} onChange={(e) => set("covered_area_sqm", e.target.value)} /></Field>
            <Field label="Storeys (e.g. S+4)"><input className="input" value={f.storeys || ""} onChange={(e) => set("storeys", e.target.value)} /></Field>
            <Field label="Height (m)"><input className="input" value={f.height_m ?? ""} onChange={(e) => set("height_m", e.target.value)} /></Field>
            <Field label="Use observed"><input className="input" value={f.use_observed || ""} onChange={(e) => set("use_observed", e.target.value)} placeholder="residential / commercial / PG ..." /></Field>
            <Field label="Source"><select className="input" value={f.source} onChange={(e) => set("source", e.target.value)}>{["FIELD_INSPECTION", "COMPLAINT", "DRONE", "COURT", "OTHER"].map((s) => <option key={s}>{s}</option>)}</select></Field>
          </div>
        </Card>
      </div>
      <Card title={`3. Violations (${Object.keys(sel).length} selected)`} actions={<div className="flex gap-2"><input className="input w-56" placeholder="search" value={q} onChange={(e) => setQ(e.target.value)} /><select className="input w-64" value={cat} onChange={(e) => setCat(e.target.value)}><option value="">All categories</option>{cats.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}</select></div>}>
        <div className="grid md:grid-cols-2 gap-2 max-h-[420px] overflow-y-auto pr-1">
          {filtered.map((v) => (
            <div key={v.code} className={`rounded-lg border p-3 text-sm cursor-pointer ${sel[v.code] ? "border-primary-400 bg-primary-50" : "border-light-border hover:border-primary-200"}`} onClick={() => toggle(v.code)}>
              <div className="flex items-start gap-2"><input type="checkbox" readOnly checked={!!sel[v.code]} className="mt-1" /><div className="flex-1"><div className="font-medium"><span className="font-mono text-xs text-primary-600 mr-1">{v.code}</span>{v.title_en}</div><div className="text-xs text-light-text-muted">{v.title_hi}</div><div className="text-[11px] text-light-text-muted mt-1">{v.contravention_of}</div><div className="flex gap-1 mt-1"><SeverityBadge s={v.severity} /><span className="badge bg-gray-100">{v.compoundable === "NO" ? "non-compoundable" : v.compoundable === "YES" ? "compoundable" : "conditionally compoundable"}</span><span className="badge bg-gray-100">SCN {v.scn_response_days_default}d · order {v.order_compliance_days_default}d</span></div></div></div>
              {sel[v.code] && <div className="mt-2 space-y-1" onClick={(e) => e.stopPropagation()}>
                <input className="input text-xs" placeholder="Remarks for this violation (printed on notice)" value={sel[v.code].remarks} onChange={(e) => setSel((s) => ({ ...s, [v.code]: { ...s[v.code], remarks: e.target.value } }))} />
                <div className="grid grid-cols-2 gap-1"><input className="input text-xs" placeholder="Permitted (e.g. S+3 / 66% / 3 m)" value={sel[v.code].details.permitted || ""} onChange={(e) => setSel((s) => ({ ...s, [v.code]: { ...s[v.code], details: { ...s[v.code].details, permitted: e.target.value } } }))} /><input className="input text-xs" placeholder="Actual found" value={sel[v.code].details.actual || ""} onChange={(e) => setSel((s) => ({ ...s, [v.code]: { ...s[v.code], details: { ...s[v.code].details, actual: e.target.value } } }))} /></div>
                <div className="text-[11px] text-light-text-muted">Evidence checklist: {v.evidence_checklist.slice(0, 4).join("; ")}</div>
              </div>}
            </div>))}
        </div>
      </Card>
      <Card title="4. Inspection report & evidence">
        <Field label="Observations (printed on the notice)" required><textarea className="input" rows={4} value={f.description || ""} onChange={(e) => set("description", e.target.value)} placeholder="Describe what was found: floors, setbacks, use, work in progress, persons met..." /></Field>
        <div className="mt-3"><Uploader kind="INSPECTION" caseId={id} onUploaded={(m) => setMedia((s) => [m, ...s])} label="Upload geotagged photos / videos (on the app these are captured in-camera)" /></div>
        <div className="mt-3"><MediaGallery items={media} /></div>
      </Card>
      <div className="flex gap-2 justify-end sticky bottom-4">
        <button className="btn-outline" onClick={() => nav(-1)}>Cancel</button>
        <button className="btn-outline" disabled={save.isPending} onClick={() => save.mutate(false)}>Save draft</button>
        <button className="btn-primary" disabled={save.isPending || !Object.keys(sel).length || !f.description || !f.address_line} onClick={() => save.mutate(true)}>Submit to AE</button>
      </div>
    </div>
  );
}
