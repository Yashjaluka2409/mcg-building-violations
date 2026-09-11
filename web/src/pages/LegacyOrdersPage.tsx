/**
 * Orders issued before the system (paper demolition / sealing / eviction orders).
 * Register of imported orders with status updates from the paper file, a form to add one order, and a bulk
 * upload from a CSV / XLSX register. Backend: services/legacy.py, api/views_legacy.py.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Download, FileUp, PlusCircle, RefreshCw, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { legacy, masters } from "@/api/endpoints";
import type { CaseListItem } from "@/api/types";
import { useAuth } from "@/store/auth";
import Uploader from "@/components/Uploader";
import { Alert, Card, Empty, Field, Modal, Pager, Spinner, StatusBadge } from "@/components/ui";

const STATUSES: [string, string][] = [
  ["ORDER_ISSUED", "Order issued - not yet served"], ["ORDER_SERVED", "Served - compliance period running"], ["EXECUTION_DUE", "Compliance period over - execution due"],
  ["APPEAL_STAY", "Stayed in appeal / court"], ["COMPLIED", "Complied by owner"], ["EXECUTED", "Demolished / sealed by MCG"], ["CLOSED", "Closed"],
  ["REGULARISED", "Regularised / compounded"], ["DROPPED", "Dropped / withdrawn"],
];
const SERVICE_MODES = ["IN_PERSON", "AFFIXATION", "POST", "SMS", "EMAIL", "WHATSAPP", "BEAT_OF_DRUM"];
const EXEC_ACTIONS = ["DEMOLITION", "PARTIAL_DEMOLITION", "SEALING", "DESEALING", "EVICTION", "REMOVAL", "ALTERATION"];
const AUTHORITIES: [string, string][] = [["DIVISIONAL_COMMISSIONER", "Divisional Commissioner"], ["COMMISSIONER_MCG", "Commissioner, MCG"], ["CIVIL_COURT", "Civil Court"],
  ["HIGH_COURT", "Punjab & Haryana High Court"], ["SUPREME_COURT", "Supreme Court"], ["NGT", "NGT"], ["OTHER", "Other"]];
const fmt = (d?: string | null) => (d ? new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "-");

export default function LegacyOrdersPage() {
  const [sp, setSp] = useSearchParams();
  const tab = sp.get("tab") || "register";
  const setTab = (t: string) => { const n = new URLSearchParams(sp); n.set("tab", t); setSp(n); };
  const user = useAuth((s) => s.user);
  const canManage = !!user && (user.permissions?.includes("LEGACY_ORDERS_MANAGE") || ["ADMIN", "COMMISSIONER", "ADDL_COMMISSIONER", "SUPER_ADMIN"].includes(user.role || ""));
  const summary = useQuery({ queryKey: ["legacy-summary"], queryFn: legacy.summary });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2"><Archive className="h-5 w-5 text-primary-500" /> Orders issued before the system</h1>
          <p className="text-sm text-light-text-muted">Demolition, sealing and eviction orders passed on paper. Bring them on record, then track service, stay, execution and closure exactly like new cases.</p>
        </div>
        {summary.data && (
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="badge bg-primary-50 text-primary-700">{summary.data.total} on record</span>
            <span className="badge bg-warning-50 text-warning-600">{summary.data.open} open</span>
            <span className="badge bg-danger-50 text-danger-600">{summary.data.execution_due} execution due</span>
            <span className="badge bg-slate-100 text-slate-700">{summary.data.stayed} stayed</span>
          </div>
        )}
      </div>
      <div className="flex gap-1 border-b border-slate-200">
        {[["register", "Register"], ...(canManage ? [["add", "Add an order"], ["bulk", "Upload a register"]] : [])].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-2 text-sm border-b-2 -mb-px ${tab === k ? "border-primary-500 text-primary-700 font-medium" : "border-transparent text-light-text-muted hover:text-light-text"}`}>{l}</button>
        ))}
      </div>
      {tab === "register" && <Register canManage={canManage} />}
      {tab === "add" && canManage && <AddOrder onDone={() => { setTab("register"); summary.refetch(); }} />}
      {tab === "bulk" && canManage && <BulkUpload onDone={() => summary.refetch()} />}
    </div>
  );
}

function Register({ canManage }: { canManage: boolean }) {
  const [sp, setSp] = useSearchParams();
  const page = Number(sp.get("page") || 1);
  const params = { status: sp.get("status") || undefined, search: sp.get("search") || undefined, page, page_size: 25 };
  const q = useQuery({ queryKey: ["legacy-orders", params], queryFn: () => legacy.list(params) });
  const [updating, setUpdating] = useState<CaseListItem | null>(null);
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); if (k !== "page") n.delete("page"); setSp(n); };
  return (
    <Card>
      <div className="flex flex-wrap gap-2 mb-3">
        <div className="relative"><Search className="h-4 w-4 absolute left-2 top-2.5 text-gray-400" /><input className="input pl-8 w-72" placeholder="Order no, PID, address, owner, register ref" defaultValue={sp.get("search") || ""} onKeyDown={(e) => { if (e.key === "Enter") set("search", (e.target as HTMLInputElement).value); }} /></div>
        <select className="input w-64" value={sp.get("status") || ""} onChange={(e) => set("status", e.target.value)}>
          <option value="">All statuses</option>
          <option value="ORDER_ISSUED,ORDER_SERVED,EXECUTION_DUE,APPEAL_STAY">Open only</option>
          {STATUSES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <button className="btn-secondary" onClick={() => q.refetch()}><RefreshCw className="h-4 w-4" /></button>
      </div>
      {q.isLoading ? <Spinner /> : !q.data?.results.length ? <Empty text="No orders on record yet. Use 'Add an order' or 'Upload a register'." /> : (
        <div className="overflow-x-auto">
          <table className="table">
            <thead><tr><th>Order</th><th>Property</th><th>Owner</th><th>Ward</th><th>Served</th><th>Compliance due</th><th>Status</th><th>Reference</th><th></th></tr></thead>
            <tbody>
              {q.data.results.map((c) => (
                <tr key={c.id}>
                  <td><Link to={`/cases/${c.id}`} className="font-medium text-primary-700">{(c as any).final_order_no || c.case_no}</Link><div className="text-[11px] text-light-text-muted">{fmt((c as any).order_issued_at)} · {c.case_no}</div></td>
                  <td className="max-w-xs"><div className="truncate">{c.address_line}</div><div className="text-[11px] text-light-text-muted">{c.pid || "no PID"}{c.locality ? ` · ${c.locality}` : ""}</div></td>
                  <td>{c.owner_name || "-"}</td>
                  <td>{c.ward_number ?? "-"}</td>
                  <td>{fmt((c as any).order_served_at)}</td>
                  <td>{fmt((c as any).compliance_due_at)}</td>
                  <td><StatusBadge status={c.status} />{c.litigation_status === "STAYED" && <div className="text-[11px] text-danger-600 mt-1">Stayed{c.stay_until ? ` till ${fmt(c.stay_until)}` : ""}</div>}</td>
                  <td className="text-xs text-light-text-muted max-w-[10rem] truncate" title={(c as any).legacy_reference}>{(c as any).legacy_reference || "-"}</td>
                  <td className="whitespace-nowrap">{canManage && <button className="btn-secondary text-xs" onClick={() => setUpdating(c)}>Update status</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager count={q.data.count} page={page} pageSize={25} onPage={(p) => set("page", String(p))} />
        </div>
      )}
      {updating && <UpdateStatusModal c={updating} onClose={() => setUpdating(null)} onDone={() => { setUpdating(null); q.refetch(); }} />}
    </Card>
  );
}

function UpdateStatusModal({ c, onClose, onDone }: { c: CaseListItem; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState<Record<string, any>>({ status: "", on_date: new Date().toISOString().slice(0, 10), remarks: "", order_reference: "", media_ids: [] });
  const set = (k: string, v: any) => setF((s) => ({ ...s, [k]: v }));
  const [err, setErr] = useState("");
  const mut = useMutation({ mutationFn: () => legacy.updateStatus(c.id, f), onSuccess: onDone, onError: (e) => setErr(errorMessage(e)) });
  const s = f.status;
  return (
    <Modal open onClose={onClose} title={`Update status from the paper file · ${c.case_no}`}>
      <div className="space-y-3">
        <div className="text-sm text-light-text-muted">{c.address_line} · currently <StatusBadge status={c.status} /></div>
        {err && <Alert kind="error">{err}</Alert>}
        <Field label="New status" required><select className="input" value={s} onChange={(e) => set("status", e.target.value)}><option value="">Select</option>{STATUSES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Date of the event" required><input type="date" className="input" value={f.on_date} onChange={(e) => set("on_date", e.target.value)} /></Field>
          <Field label="Authorising reference (file / order no.)"><input className="input" value={f.order_reference} onChange={(e) => set("order_reference", e.target.value)} /></Field>
        </div>
        {(s === "ORDER_SERVED" || s === "EXECUTION_DUE") && <Field label="Mode of service"><select className="input" value={f.served_mode || ""} onChange={(e) => set("served_mode", e.target.value)}><option value="">Select</option>{SERVICE_MODES.map((m) => <option key={m}>{m}</option>)}</select></Field>}
        {(s === "EXECUTED" || s === "COMPLIED") && (
          <div className="grid grid-cols-2 gap-2">
            <Field label="Action"><select className="input" value={f.execution_action || ""} onChange={(e) => set("execution_action", e.target.value)}><option value="">Default for the order</option>{EXEC_ACTIONS.map((m) => <option key={m}>{m}</option>)}</select></Field>
            <Field label="Cost incurred (₹)"><input type="number" className="input" value={f.cost_incurred_inr || ""} onChange={(e) => set("cost_incurred_inr", e.target.value || null)} /></Field>
          </div>
        )}
        {s === "APPEAL_STAY" && (
          <div className="grid grid-cols-3 gap-2">
            <Field label="Authority / court" required><select className="input" value={f.appeal_authority || ""} onChange={(e) => set("appeal_authority", e.target.value)}><option value="">Select</option>{AUTHORITIES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
            <Field label="Appeal / CWP no."><input className="input" value={f.appeal_no || ""} onChange={(e) => set("appeal_no", e.target.value)} /></Field>
            <Field label="Stay until"><input type="date" className="input" value={f.stay_until || ""} onChange={(e) => set("stay_until", e.target.value || null)} /></Field>
          </div>
        )}
        {["CLOSED", "REGULARISED", "DROPPED"].includes(s) && <Field label="Reason for closure"><input className="input" value={f.closure_reason || ""} onChange={(e) => set("closure_reason", e.target.value)} /></Field>}
        <Field label="Remarks"><textarea className="input" rows={2} value={f.remarks} onChange={(e) => set("remarks", e.target.value)} /></Field>
        <Field label="Scanned documents (delivery report, stay order, demolition report)" hint="Optional - paper evidence scanned from the file">
          <Uploader kind={s === "APPEAL_STAY" ? "STAY_ORDER" : s === "EXECUTED" ? "EXECUTION" : "ORDER_DELIVERY"} caseId={c.id} onUploaded={(m) => set("media_ids", [...f.media_ids, m.id])} accept="image/*,.pdf" label="Attach scan" />
          {f.media_ids.length > 0 && <div className="text-xs text-success-700 mt-1">{f.media_ids.length} file(s) attached</div>}
        </Field>
        <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!s || mut.isPending} onClick={() => mut.mutate()}>{mut.isPending ? "Saving…" : "Record status"}</button></div>
      </div>
    </Modal>
  );
}

function AddOrder({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const orderTypes = useQuery({ queryKey: ["order-types"], queryFn: masters.orderTypes });
  const vtypes = useQuery({ queryKey: ["violation-types"], queryFn: masters.violationTypes });
  const wards = useQuery({ queryKey: ["wards"], queryFn: () => masters.wards() });
  const [f, setF] = useState<Record<string, any>>({ order_type: "DEMOLITION_ORDER_261", order_date: "", order_no: "", compliance_days: 15, current_status: "", media_ids: [], violations: [] as string[], stay_granted: false });
  const set = (k: string, v: any) => setF((s) => ({ ...s, [k]: v }));
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const finalOrders = useMemo(() => (orderTypes.data || []).filter((o: any) => o.kind === "ORDER"), [orderTypes.data]);
  const mut = useMutation({
    mutationFn: () => {
      const payload: Record<string, any> = { ...f, violations: (f.violations as string[]).map((code, i) => ({ code, is_primary: i === 0 })) };
      for (const k of Object.keys(payload)) if (payload[k] === "" || payload[k] === null) delete payload[k];
      return legacy.create(payload);
    },
    onSuccess: (c) => { setOk(`Recorded as ${c.case_no}`); setErr(""); qc.invalidateQueries({ queryKey: ["legacy-orders"] }); setF({ order_type: f.order_type, order_date: "", order_no: "", compliance_days: 15, current_status: "", media_ids: [], violations: [], stay_granted: false, issued_by_name: f.issued_by_name, issued_by_designation: f.issued_by_designation, legacy_reference: f.legacy_reference }); onDone(); },
    onError: (e) => { setErr(errorMessage(e)); setOk(""); },
  });
  const s = f.current_status;
  return (
    <Card title="Record one order from the paper file">
      {err && <Alert kind="error">{err}</Alert>}{ok && <Alert kind="success">{ok}</Alert>}
      <div className="grid md:grid-cols-3 gap-3">
        <Field label="Original order number" required><input className="input" value={f.order_no} onChange={(e) => set("order_no", e.target.value)} placeholder="MCG/JC-2/DEMO/2023/0412" /></Field>
        <Field label="Date of the order" required><input type="date" className="input" value={f.order_date} onChange={(e) => set("order_date", e.target.value)} /></Field>
        <Field label="Order type" required><select className="input" value={f.order_type} onChange={(e) => set("order_type", e.target.value)}>{finalOrders.map((o: any) => <option key={o.code} value={o.code}>{o.title_en}</option>)}</select></Field>
        <Field label="Signed by (name)"><input className="input" value={f.issued_by_name || ""} onChange={(e) => set("issued_by_name", e.target.value)} /></Field>
        <Field label="Designation"><input className="input" value={f.issued_by_designation || ""} onChange={(e) => set("issued_by_designation", e.target.value)} placeholder="Joint Commissioner, Zone 2" /></Field>
        <Field label="Compliance period given (days)"><input type="number" className="input" value={f.compliance_days ?? ""} onChange={(e) => set("compliance_days", e.target.value === "" ? null : Number(e.target.value))} /></Field>
        <Field label="PID"><input className="input" value={f.pid || ""} onChange={(e) => set("pid", e.target.value)} /></Field>
        <Field label="Address" required={!f.pid}><input className="input" value={f.address_line || ""} onChange={(e) => set("address_line", e.target.value)} /></Field>
        <Field label="Locality / sector"><input className="input" value={f.locality || ""} onChange={(e) => set("locality", e.target.value)} /></Field>
        <Field label="Ward"><select className="input" value={f.ward_number || ""} onChange={(e) => set("ward_number", e.target.value ? Number(e.target.value) : null)}><option value="">Unknown</option>{(wards.data || []).map((w: any) => <option key={w.id} value={w.number}>Ward {w.number}{w.name_en ? ` - ${w.name_en}` : ""}</option>)}</select></Field>
        <Field label="Owner / noticee"><input className="input" value={f.owner_name || ""} onChange={(e) => set("owner_name", e.target.value)} /></Field>
        <Field label="Mobile"><input className="input" value={f.pid_linked_mobile || ""} onChange={(e) => set("pid_linked_mobile", e.target.value)} /></Field>
        <Field label="Violations covered by the order" hint="Hold Ctrl / Cmd to select several">
          <select multiple className="input h-28" value={f.violations} onChange={(e) => set("violations", Array.from(e.target.selectedOptions).map((o) => o.value))}>{(vtypes.data || []).map((v: any) => <option key={v.code} value={v.code}>{v.title_en}</option>)}</select>
        </Field>
        <Field label="What the order says / observations"><textarea className="input" rows={4} value={f.description || ""} onChange={(e) => set("description", e.target.value)} /></Field>
        <Field label="Register / file reference"><input className="input" value={f.legacy_reference || ""} onChange={(e) => set("legacy_reference", e.target.value)} placeholder="Demolition order register 2023-24, p.61" /></Field>
      </div>
      <h3 className="font-medium mt-5 mb-2">Where does the file stand today?</h3>
      <div className="grid md:grid-cols-3 gap-3">
        <Field label="Served on"><input type="date" className="input" value={f.served_on || ""} onChange={(e) => set("served_on", e.target.value || null)} /></Field>
        <Field label="Mode of service"><select className="input" value={f.served_mode || ""} onChange={(e) => set("served_mode", e.target.value)}><option value="">Select</option>{SERVICE_MODES.map((m) => <option key={m}>{m}</option>)}</select></Field>
        <Field label="Current status" hint="Leave blank to derive from the dates below"><select className="input" value={s} onChange={(e) => set("current_status", e.target.value)}><option value="">Derive from dates</option>{STATUSES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Executed / complied on"><input type="date" className="input" value={f.executed_on || ""} onChange={(e) => set("executed_on", e.target.value || null)} /></Field>
        <Field label="Execution action"><select className="input" value={f.execution_action || ""} onChange={(e) => set("execution_action", e.target.value)}><option value="">Default for the order</option>{EXEC_ACTIONS.map((m) => <option key={m}>{m}</option>)}</select></Field>
        <Field label="Executed by"><select className="input" value={f.execution_mode || ""} onChange={(e) => set("execution_mode", e.target.value)}><option value="">Corporation</option><option value="CORPORATION">Corporation</option><option value="OWNER_SELF">Owner complied</option></select></Field>
        <Field label="Appeal / writ before"><select className="input" value={f.appeal_authority || ""} onChange={(e) => set("appeal_authority", e.target.value)}><option value="">None</option>{AUTHORITIES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Appeal / CWP number"><input className="input" value={f.appeal_no || ""} onChange={(e) => set("appeal_no", e.target.value)} /></Field>
        <Field label="Stay"><label className="flex items-center gap-2 text-sm mt-2"><input type="checkbox" checked={!!f.stay_granted} onChange={(e) => set("stay_granted", e.target.checked)} /> Stay / status quo granted</label>{f.stay_granted && <input type="date" className="input mt-1" value={f.stay_until || ""} onChange={(e) => set("stay_until", e.target.value || null)} placeholder="Stay until" />}</Field>
        <Field label="Closed on"><input type="date" className="input" value={f.closed_on || ""} onChange={(e) => set("closed_on", e.target.value || null)} /></Field>
        <Field label="Authorising reference for this entry" hint="Office order / noting under which the backlog is being brought on record"><input className="input" value={f.order_reference || ""} onChange={(e) => set("order_reference", e.target.value)} /></Field>
        <Field label="Remarks"><input className="input" value={f.remarks || ""} onChange={(e) => set("remarks", e.target.value)} /></Field>
      </div>
      <div className="mt-3">
        <Field label="Scanned copy of the signed order (PDF / photo)" hint="Attached to the order; the public verification page will show 'order on record (paper)'">
          <Uploader kind="LEGACY_ORDER" onUploaded={(m) => set("media_ids", [...f.media_ids, m.id])} accept="image/*,.pdf" label="Attach the scanned order" />
          {f.media_ids.length > 0 && <div className="text-xs text-success-700 mt-1">{f.media_ids.length} file(s) attached</div>}
        </Field>
      </div>
      <div className="flex justify-end mt-3"><button className="btn-primary" disabled={mut.isPending || !f.order_no || !f.order_date} onClick={() => mut.mutate()}><PlusCircle className="h-4 w-4" /> {mut.isPending ? "Recording…" : "Record this order"}</button></div>
    </Card>
  );
}

function BulkUpload({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const batches = useQuery({ queryKey: ["legacy-batches"], queryFn: legacy.batches });
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [ref, setRef] = useState("");
  const [err, setErr] = useState("");
  const mut = useMutation({
    mutationFn: () => { const fd = new FormData(); fd.append("file", file!); fd.append("title", title || file!.name); fd.append("order_reference", ref); return legacy.bulk(fd); },
    onSuccess: () => { setFile(null); setErr(""); batches.refetch(); qc.invalidateQueries({ queryKey: ["legacy-orders"] }); onDone(); },
    onError: (e) => setErr(errorMessage(e)),
  });
  return (
    <div className="space-y-4">
      <Card title="Upload a register (CSV / XLSX)">
        <p className="text-sm text-light-text-muted mb-3">One row per order. Download the template, fill it from the demolition / sealing order registers (dates as YYYY-MM-DD; several violation codes separated by ;), and upload. Rows with problems are reported and can be corrected and re-uploaded; orders already on record are skipped.</p>
        {err && <Alert kind="error">{err}</Alert>}
        <div className="grid md:grid-cols-3 gap-3">
          <Field label="Register title"><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Zone 3 demolition order register 2022-24" /></Field>
          <Field label="Authorising reference"><input className="input" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="Commissioner's order no. / noting" /></Field>
          <Field label="File" required><input type="file" accept=".csv,.xlsx" className="input" onChange={(e) => setFile(e.target.files?.[0] || null)} /></Field>
        </div>
        <div className="flex gap-2 mt-3">
          <a className="btn-secondary" href={legacy.templateUrl} target="_blank" rel="noreferrer"><Download className="h-4 w-4" /> Template</a>
          <button className="btn-primary" disabled={!file || mut.isPending} onClick={() => mut.mutate()}><FileUp className="h-4 w-4" /> {mut.isPending ? "Importing…" : "Import register"}</button>
        </div>
      </Card>
      <Card title="Previous uploads">
        {batches.isLoading ? <Spinner /> : !batches.data?.length ? <Empty text="No registers uploaded yet" /> : (
          <div className="space-y-3">
            {batches.data.map((b: any) => (
              <div key={b.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <div className="flex flex-wrap justify-between gap-2"><div className="font-medium">{b.title}</div><div className="text-light-text-muted">{fmt(b.created_at)} · {b.created_by?.name}</div></div>
                <div className="text-xs mt-1"><span className="text-success-700">{b.imported} imported</span> · {b.total_rows} rows · <span className={b.errors.length ? "text-danger-600" : ""}>{b.errors.length} error(s)</span></div>
                {b.errors.length > 0 && <ul className="mt-2 text-xs text-danger-600 list-disc pl-5 max-h-40 overflow-auto">{b.errors.map((e: any, i: number) => <li key={i}>Row {e.row}{e.order_no ? ` (${e.order_no})` : ""}: {e.error}</li>)}</ul>}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
