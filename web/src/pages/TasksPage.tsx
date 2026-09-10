import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Crosshair, Download, MapPin, Navigation, Play, Upload, XCircle } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { masters, property, tasks } from "@/api/endpoints";
import { api, errorMessage } from "@/api/client";
import type { InspectionTask } from "@/api/types";
import MapView from "@/components/MapView";
import Uploader from "@/components/Uploader";
import { Alert, Empty, Field, Modal, Pager, Spinner } from "@/components/ui";
import { fmtDate, fmtDateTime } from "@/utils/format";
import { useAuth } from "@/store/auth";

const CATS = [["VERIFICATION", "Routine verification"], ["PG_HOSTEL", "Paying guest / hostel check"], ["COMPLAINT", "Complaint verification"], ["DRONE_FLAG", "Drone / satellite change"], ["COURT_DIRECTION", "Court / appellate direction"], ["SANCTION_FOLLOWUP", "Sanctioned plan follow-up"], ["GOVT_LAND", "Government land watch"], ["RE_INSPECTION", "Re-inspection"], ["OTHER", "Other"]];
const TSTAT: Record<string, string> = { ASSIGNED: "bg-warning-50 text-warning-600", UNASSIGNED: "bg-gray-100 text-gray-600", IN_PROGRESS: "bg-accent-100 text-accent-700", VIOLATION_RECORDED: "bg-danger-50 text-danger-600", NO_VIOLATION: "bg-success-50 text-success-700", NOT_FOUND: "bg-gray-100 text-gray-700", CANCELLED: "bg-gray-100 text-gray-400" };

/** Planned inspections: the JC/AE pushes PIDs or map points to the JE; the JE starts them on site
 *  (within the geofence) and either records a violation or reports "no violation" with a photo. */
export default function TasksPage() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const perms = user?.permissions || [];
  const canAssign = perms.includes("TASKS_ASSIGN");
  const [sp, setSp] = useSearchParams();
  const p = Object.fromEntries(sp.entries());
  const page = Number(p.page || 1);
  const [view, setView] = useState<"list" | "map">("list");
  const [modal, setModal] = useState<null | "new" | "bulk" | "assign" | "close">(null);
  const [sel, setSel] = useState<InspectionTask | null>(null);
  const [msg, setMsg] = useState<{ kind: "info" | "error" | "success"; text: string } | null>(null);
  const params: Record<string, unknown> = { ...p, page, page_size: 25, ordering: p.ordering || "-created_at" };
  if (!canAssign) params.mine = 1;
  const q = useQuery({ queryKey: ["tasks", params], queryFn: () => tasks.list(params) });
  const counts = useQuery({ queryKey: ["task-counts"], queryFn: tasks.counts });
  const geo = useQuery({ queryKey: ["tasks-geo", p], queryFn: () => tasks.geojson({ ...p, ...(canAssign ? {} : { mine: 1 }) }), enabled: view === "map" });
  const jes = useQuery({ queryKey: ["officers", "JE"], queryFn: () => masters.officers({ role: "JE" }), enabled: canAssign });
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); if (k !== "page") n.delete("page"); setSp(n); };
  const refresh = () => { qc.invalidateQueries({ queryKey: ["tasks"] }); qc.invalidateQueries({ queryKey: ["task-counts"] }); qc.invalidateQueries({ queryKey: ["tasks-geo"] }); };
  const locate = () => new Promise<GeolocationPosition>((res, rej) => navigator.geolocation ? navigator.geolocation.getCurrentPosition(res, rej, { enableHighAccuracy: true, timeout: 10000 }) : rej(new Error("no geolocation")));
  const start = async (t: InspectionTask) => {
    setMsg(null);
    try {
      const pos = await locate();
      const d = await tasks.distance(t.id, pos.coords.latitude, pos.coords.longitude);
      if (!d.within) { setMsg({ kind: "error", text: `You are ${Math.round(d.distance_m || 0)} m from the property. Move within ${d.geofence_m} m to start this inspection.` }); return; }
      await tasks.start(t.id, pos.coords.latitude, pos.coords.longitude, Math.round(pos.coords.accuracy));
      refresh();
      nav(`/cases/new?task=${t.id}`);
    } catch (e) { setMsg({ kind: "error", text: errorMessage(e) }); }
  };
  const cancel = useMutation({ mutationFn: (t: InspectionTask) => tasks.cancel(t.id, "Cancelled by " + user?.name), onSuccess: refresh });
  const c = counts.data || {};
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3"><div><h1 className="page-title">Planned inspections</h1><p className="page-sub">{canAssign ? "Push PIDs or map points to the field for verification - single, bulk (e.g. all PGs) or from the map. Inspections can only be started within 100 m of the property." : "Inspections assigned to you. Start each one on site - the app checks that you are within 100 m of the property."}</p></div><div className="flex-1" />
        {canAssign && <><a className="btn-outline" href="#" onClick={async (e) => { e.preventDefault(); const r = await api.get("/inspections/tasks/template/", { responseType: "blob" }); const u = URL.createObjectURL(r.data); const a = document.createElement("a"); a.href = u; a.download = "planned_inspections_template.csv"; a.click(); }}><Download className="h-4 w-4" />CSV template</a><button className="btn-outline" onClick={() => setModal("bulk")}><Upload className="h-4 w-4" />Bulk push (PID list)</button><button className="btn-primary" onClick={() => setModal("new")}><Crosshair className="h-4 w-4" />Push one property</button></>}
      </div>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-sm">{[["assigned_to_me", "Assigned to me", "bg-warning-50"], ["open", "Open", "bg-primary-50"], ["unassigned", "Unassigned", "bg-gray-100"], ["overdue", "Overdue", "bg-danger-50"], ["violation_recorded", "Violation recorded", "bg-danger-100"], ["no_violation", "No violation", "bg-success-50"]].map(([k, l, cls]) => <button key={k} className={`card p-3 text-left ${cls}`} onClick={() => set("status", k === "open" ? "" : k === "violation_recorded" ? "VIOLATION_RECORDED" : k === "no_violation" ? "NO_VIOLATION" : k === "unassigned" ? "UNASSIGNED" : "")}><div className="text-2xl font-bold">{c[k] ?? 0}</div><div className="text-xs">{l}</div></button>)}</div>
      <div className="card p-3 flex flex-wrap gap-2 items-center">
        <input className="input w-64" placeholder="PID, address, owner, batch" defaultValue={p.search || ""} onKeyDown={(e) => e.key === "Enter" && set("search", (e.target as HTMLInputElement).value)} />
        <select className="input w-44" value={p.status || ""} onChange={(e) => set("status", e.target.value)}><option value="">All statuses</option>{Object.keys(TSTAT).map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}</select>
        <select className="input w-52" value={p.category || ""} onChange={(e) => set("category", e.target.value)}><option value="">All categories</option>{CATS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        {canAssign && <select className="input w-52" value={p.assigned_to || ""} onChange={(e) => set("assigned_to", e.target.value)}><option value="">Any officer</option>{jes.data?.map((o) => <option key={o.user_id} value={o.user_id}>{o.name}</option>)}</select>}
        <label className="text-sm flex items-center gap-1"><input type="checkbox" checked={p.overdue === "1"} onChange={(e) => set("overdue", e.target.checked ? "1" : "")} />Overdue</label>
        <div className="flex-1" /><div className="flex gap-1">{(["list", "map"] as const).map((v) => <button key={v} className={view === v ? "btn-primary" : "btn-outline"} onClick={() => setView(v)}>{v === "list" ? "List" : "Map"}</button>)}</div>
      </div>
      {view === "map" ? <MapView points={geo.data} fit legend height="calc(100vh - 380px)" onOpenCase={(id) => nav(`/cases/${id}`)} onOpenTask={(id) => { const t = q.data?.results.find((x) => x.id === id); if (t) { setSel(t); setView("list"); } }} /> : (
        <div className="card overflow-x-auto">{q.isLoading ? <Spinner /> : !q.data?.results.length ? <Empty text="No planned inspections" /> : (
          <table className="table"><thead><tr><th>#</th><th>Property</th><th>Category / instructions</th><th>Assigned to</th><th>Due</th><th>Status</th><th>Outcome</th><th></th></tr></thead>
            <tbody>{q.data.results.map((t) => <tr key={t.id} className="hover:bg-primary-50/40">
              <td className="text-xs font-mono">{t.id}{t.batch_title && <div className="text-[10px] text-light-text-muted max-w-[120px] truncate">{t.batch_title}</div>}</td>
              <td className="max-w-[260px]"><div className="font-medium truncate">{t.address || "(map point)"}</div><div className="text-xs text-light-text-muted">{t.pid ? `PID ${t.pid} · ` : ""}{t.owner_name}{t.ward_number ? ` · Ward ${t.ward_number}` : ""}{t.latitude ? <span className="ml-1"><MapPin className="h-3 w-3 inline" />{Number(t.latitude).toFixed(4)},{Number(t.longitude).toFixed(4)}</span> : <span className="text-warning-600"> · no coordinates</span>}</div></td>
              <td className="max-w-[300px] text-xs"><span className="badge bg-primary-50 text-primary-700">{t.category_display}</span><div className="truncate" title={t.instructions}>{t.instructions}</div></td>
              <td className="text-xs">{t.assigned_to?.name || <span className="text-warning-600">unassigned</span>}<div className="text-light-text-muted">by {t.created_by?.name}</div></td>
              <td className={`text-xs ${t.is_overdue ? "text-danger-600 font-semibold" : ""}`}>{fmtDate(t.due_at)}</td>
              <td><span className={`badge ${TSTAT[t.status]}`}>{t.status_display}</span>{t.started_at && <div className="text-[10px] text-light-text-muted">on site {fmtDateTime(t.started_at)} · {t.start_distance_m != null ? `${Number(t.start_distance_m).toFixed(0)} m` : ""}</div>}</td>
              <td className="text-xs max-w-[200px]">{t.case_no ? <button className="text-primary-700 font-mono underline" onClick={() => nav(`/cases/${t.case_id}`)}>{t.case_no}</button> : t.outcome_remarks ? <span className="truncate block" title={t.outcome_remarks}>{t.outcome_remarks}</span> : "-"}</td>
              <td className="text-xs whitespace-nowrap"><div className="flex gap-1">
                {["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"].includes(t.status) && (t.assigned_to?.id === user?.id || !t.assigned_to) && <button className="btn-accent px-2 py-1" title="Start on site (geofence 100 m)" onClick={() => start(t)}><Play className="h-3 w-3" />{t.status === "IN_PROGRESS" ? "Continue" : "Start"}</button>}
                {t.status === "IN_PROGRESS" && t.assigned_to?.id === user?.id && <button className="btn-outline px-2 py-1" onClick={() => { setSel(t); setModal("close"); }}>No violation</button>}
                {canAssign && ["ASSIGNED", "UNASSIGNED", "IN_PROGRESS"].includes(t.status) && <><button className="btn-outline px-2 py-1" onClick={() => { setSel(t); setModal("assign"); }}>Assign</button><button className="btn-ghost px-2 py-1" title="Cancel" onClick={() => confirm("Cancel this inspection?") && cancel.mutate(t)}><XCircle className="h-4 w-4" /></button></>}
              </div></td>
            </tr>)}</tbody></table>)}
          {q.data && <div className="px-3 pb-3"><Pager count={q.data.count} page={page} pageSize={25} onPage={(n) => set("page", String(n))} /></div>}
        </div>)}
      <NewTaskModal open={modal === "new"} onClose={() => setModal(null)} onDone={() => { setModal(null); refresh(); setMsg({ kind: "success", text: "Inspection pushed to the field" }); }} />
      <BulkModal open={modal === "bulk"} onClose={() => setModal(null)} onDone={(b) => { setModal(null); refresh(); setMsg({ kind: b.errors.length ? "info" : "success", text: `Batch "${b.title}": ${b.total} inspection(s) pushed${b.errors.length ? `, ${b.errors.length} row(s) skipped: ${b.errors.slice(0, 3).map((e: { row: number; error: string }) => `row ${e.row} ${e.error}`).join("; ")}` : ""}` }); }} />
      <Modal open={modal === "assign" && !!sel} onClose={() => setModal(null)} title={`Assign inspection #${sel?.id}`}>{sel && <AssignForm t={sel} jes={jes.data || []} onDone={() => { setModal(null); refresh(); }} />}</Modal>
      <Modal open={modal === "close" && !!sel} onClose={() => setModal(null)} title={`Report: no violation at ${sel?.address || sel?.pid}`}>{sel && <CloseForm t={sel} onDone={() => { setModal(null); refresh(); }} locate={locate} />}</Modal>
    </div>
  );
}

function NewTaskModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState<Record<string, any>>({ category: "PG_HOSTEL", priority: "NORMAL", due_days: 7 });
  const [err, setErr] = useState("");
  const [pidInfo, setPidInfo] = useState<any>(null);
  const jes = useQuery({ queryKey: ["officers", "JE"], queryFn: () => masters.officers({ role: "JE" }) });
  const lookup = useMutation({ mutationFn: () => property.lookupPid(f.pid), onSuccess: (d) => { setPidInfo(d); setF((s) => ({ ...s, address: d.address, owner_name: d.owner_name, owner_mobile: d.mobile, latitude: d.latitude, longitude: d.longitude })); }, onError: (e) => setErr(errorMessage(e)) });
  const save = useMutation({ mutationFn: () => tasks.create({ ...f, latitude: f.latitude || null, longitude: f.longitude || null, assigned_to: f.assigned_to || null }), onSuccess: () => { setF({ category: "PG_HOSTEL", priority: "NORMAL", due_days: 7 }); setPidInfo(null); onDone(); }, onError: (e) => setErr(errorMessage(e)) });
  return (
    <Modal open={open} onClose={onClose} title="Push a property for field verification" wide>
      <div className="space-y-3">
        {err && <Alert kind="error">{err}</Alert>}
        <div className="grid md:grid-cols-2 gap-3">
          <div className="space-y-2">
            <Field label="Property ID (PID)"><div className="flex gap-2"><input className="input font-mono" value={f.pid || ""} onChange={(e) => setF({ ...f, pid: e.target.value.toUpperCase() })} /><button className="btn-accent" disabled={!f.pid || lookup.isPending} onClick={() => lookup.mutate()}>Fetch</button></div></Field>
            {pidInfo && <div className="text-xs bg-accent-50 border border-accent-100 rounded p-2">{pidInfo.owner_name} · {pidInfo.mobile} · {pidInfo.property_type} · Ward {pidInfo.ward_no}</div>}
            <Field label="Address"><textarea className="input" rows={2} value={f.address || ""} onChange={(e) => setF({ ...f, address: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-2"><Field label="Owner"><input className="input" value={f.owner_name || ""} onChange={(e) => setF({ ...f, owner_name: e.target.value })} /></Field><Field label="Mobile"><input className="input" value={f.owner_mobile || ""} onChange={(e) => setF({ ...f, owner_mobile: e.target.value })} /></Field><Field label="Category"><select className="input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{CATS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field><Field label="Priority"><select className="input" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}>{["LOW", "NORMAL", "HIGH", "URGENT"].map((x) => <option key={x}>{x}</option>)}</select></Field><Field label="Assign to JE" hint="blank = JE of the ward automatically"><select className="input" value={f.assigned_to || ""} onChange={(e) => setF({ ...f, assigned_to: e.target.value ? Number(e.target.value) : null })}><option value="">Auto (by ward)</option>{jes.data?.map((o) => <option key={o.user_id} value={o.user_id}>{o.name}</option>)}</select></Field><Field label="Days to complete"><input type="number" className="input" value={f.due_days} onChange={(e) => setF({ ...f, due_days: Number(e.target.value) })} /></Field></div>
            <Field label="Instructions for the field officer" required><textarea className="input" rows={3} value={f.instructions || ""} onChange={(e) => setF({ ...f, instructions: e.target.value })} placeholder="e.g. Verify whether the premises are used as a PG without change of land use; count rooms and occupants; check fire exits." /></Field>
          </div>
          <div><div className="label">Point on map (click to set)</div><MapView height="360px" marker={f.latitude && f.longitude ? [Number(f.latitude), Number(f.longitude)] : null} onClick={(lat, lng) => setF({ ...f, latitude: lat.toFixed(7), longitude: lng.toFixed(7) })} /><div className="text-xs text-light-text-muted mt-1">{f.latitude ? `${Number(f.latitude).toFixed(6)}, ${Number(f.longitude).toFixed(6)}` : "No point yet - the JE's start location will become the point if left blank"}</div></div>
        </div>
        <div className="flex justify-end gap-2"><button className="btn-outline" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={(!f.pid && !f.address && !f.latitude) || !f.instructions || save.isPending} onClick={() => save.mutate()}><Navigation className="h-4 w-4" />Push to field</button></div>
      </div>
    </Modal>
  );
}

function BulkModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: (b: any) => void }) {
  const [f, setF] = useState<Record<string, any>>({ category: "PG_HOSTEL", due_days: 7, lookup_pid: true });
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState("");
  const jes = useQuery({ queryKey: ["officers", "JE"], queryFn: () => masters.officers({ role: "JE" }) });
  const up = useMutation({ mutationFn: () => { const fd = new FormData(); fd.append("file", file!); fd.append("title", f.title || ""); fd.append("category", f.category); fd.append("instructions", f.instructions || ""); fd.append("due_days", String(f.due_days)); if (f.assign_to) fd.append("assign_to", String(f.assign_to)); fd.append("lookup_pid", f.lookup_pid ? "1" : "0"); return tasks.bulkUpload(fd); }, onSuccess: onDone, onError: (e) => setErr(errorMessage(e)) });
  return (
    <Modal open={open} onClose={onClose} title="Bulk push - e.g. all PGs from the PID database">
      <div className="space-y-3">
        {err && <Alert kind="error">{err}</Alert>}
        <Alert kind="info">Upload a CSV/XLSX with the template columns (pid, address, latitude, longitude, ward_number, owner_name, owner_mobile, category, instructions, priority, assign_to_mobile). Rows with only a PID are completed from the DULB property record. Each row becomes one planned inspection, auto-assigned to the JE of its ward unless an officer is given.</Alert>
        <Field label="Batch title" required><input className="input" value={f.title || ""} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="PG verification drive - Zone 2, Sept 2026" /></Field>
        <div className="grid grid-cols-2 gap-2"><Field label="Default category"><select className="input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{CATS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field><Field label="Days to complete"><input type="number" className="input" value={f.due_days} onChange={(e) => setF({ ...f, due_days: Number(e.target.value) })} /></Field><Field label="Assign all to (optional)"><select className="input" value={f.assign_to || ""} onChange={(e) => setF({ ...f, assign_to: e.target.value ? Number(e.target.value) : null })}><option value="">Auto by ward</option>{jes.data?.map((o) => <option key={o.user_id} value={o.user_id}>{o.name}</option>)}</select></Field><Field label="Complete rows from PID database"><label className="text-sm flex items-center gap-2 mt-2"><input type="checkbox" checked={!!f.lookup_pid} onChange={(e) => setF({ ...f, lookup_pid: e.target.checked })} />Look up PIDs</label></Field></div>
        <Field label="Default instructions"><textarea className="input" rows={3} value={f.instructions || ""} onChange={(e) => setF({ ...f, instructions: e.target.value })} /></Field>
        <Field label="File" required><input type="file" accept=".csv,.xlsx" className="input" onChange={(e) => setFile(e.target.files?.[0] || null)} /></Field>
        <div className="flex justify-end gap-2"><button className="btn-outline" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!file || !f.title || up.isPending} onClick={() => up.mutate()}><Upload className="h-4 w-4" />{up.isPending ? "Pushing…" : "Push to field"}</button></div>
      </div>
    </Modal>
  );
}

function AssignForm({ t, jes, onDone }: { t: InspectionTask; jes: { user_id: number; name: string }[]; onDone: () => void }) {
  const [to, setTo] = useState<number | null>(t.assigned_to?.id || null);
  const [remarks, setRemarks] = useState("");
  const [err, setErr] = useState("");
  const m = useMutation({ mutationFn: () => tasks.assign(t.id, to!, remarks), onSuccess: onDone, onError: (e) => setErr(errorMessage(e)) });
  return <div className="space-y-3">{err && <Alert kind="error">{err}</Alert>}<Field label="Field officer" required><select className="input" value={to || ""} onChange={(e) => setTo(e.target.value ? Number(e.target.value) : null)}><option value="">-</option>{jes.map((o) => <option key={o.user_id} value={o.user_id}>{o.name}</option>)}</select></Field><Field label="Remarks"><input className="input" value={remarks} onChange={(e) => setRemarks(e.target.value)} /></Field><div className="flex justify-end"><button className="btn-primary" disabled={!to || m.isPending} onClick={() => m.mutate()}>Assign</button></div></div>;
}

function CloseForm({ t, onDone, locate }: { t: InspectionTask; onDone: () => void; locate: () => Promise<GeolocationPosition> }) {
  const [outcome, setOutcome] = useState("NO_VIOLATION");
  const [remarks, setRemarks] = useState("");
  const [media, setMedia] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const UploaderLazy = Uploader;
  const m = useMutation({ mutationFn: async () => { const pos = await locate(); return tasks.close(t.id, { outcome, remarks, media_ids: media.map((x) => x.id), latitude: pos.coords.latitude, longitude: pos.coords.longitude }); }, onSuccess: onDone, onError: (e) => setErr(errorMessage(e)) });
  return <div className="space-y-3">{err && <Alert kind="error">{err}</Alert>}<Alert kind="info">File this on site: a geotagged photograph of the property is mandatory and your location must be within {t.geofence_m} m.</Alert><Field label="Outcome"><select className="input" value={outcome} onChange={(e) => setOutcome(e.target.value)}><option value="NO_VIOLATION">Inspected - no violation found</option><option value="NOT_FOUND">Property not traceable</option></select></Field><Field label="Report" required><textarea className="input" rows={4} value={remarks} onChange={(e) => setRemarks(e.target.value)} /></Field><Field label="Photograph of the property" required><UploaderLazy kind="TASK_EVIDENCE" accept="image/*,video/*" requireGeo onUploaded={(x: any) => setMedia((s) => [...s, x])} /></Field><div className="text-xs">{media.length} file(s) attached</div><div className="flex justify-end"><button className="btn-primary" disabled={!remarks || !media.length || m.isPending} onClick={() => m.mutate()}>Submit report</button></div></div>;
}
