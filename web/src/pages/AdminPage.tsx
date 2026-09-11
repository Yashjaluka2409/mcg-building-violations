import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { admin, branches as branchesApi, masters } from "@/api/endpoints";
import { api as apiClient } from "@/api/client";
import { errorMessage } from "@/api/client";
import type { Branch, PermMatrix, RulesMatrix, WorkflowSetting } from "@/api/types";
import { Alert, Card, Field, Modal, Spinner } from "@/components/ui";
import { fmtDateTime } from "@/utils/format";
import { useAuth } from "@/store/auth";
import { useWorkflowConfig } from "@/hooks/useWorkflowConfig";
import { useTranslation } from "react-i18next";

/** Administration: everything the admin can change without a code release. Every save asks for the
 *  office-order reference and is written to the admin audit log. */
export default function AdminPage() {
  const user = useAuth((s) => s.user);
  const perms = user?.permissions || [];
  const tabs = [
    { k: "hierarchy", l: "Hierarchy", show: perms.includes("WORKFLOW_CONFIGURE") },
    { k: "rules", l: "Workflow rules", show: perms.includes("WORKFLOW_CONFIGURE") },
    { k: "settings", l: "Routing & guards", show: perms.includes("WORKFLOW_CONFIGURE") },
    { k: "permissions", l: "Access control", show: perms.includes("ACCESS_CONFIGURE") },
    { k: "branches", l: "Branches", show: perms.includes("BRANCH_MANAGE") },
    { k: "reassign", l: "Re-assign cases", show: perms.includes("CASE_REASSIGN") },
    { k: "sla", l: "SLA & order periods", show: perms.includes("MASTERS_MANAGE") || perms.includes("WORKFLOW_CONFIGURE") },
    { k: "audit", l: "Admin audit log", show: perms.includes("AUDIT_VIEW") || perms.includes("WORKFLOW_CONFIGURE") || perms.includes("ACCESS_CONFIGURE") || perms.includes("OFFICERS_MANAGE") },
  ].filter((t) => t.show);
  const [tab, setTab] = useState(tabs[0]?.k || "hierarchy");
  return (
    <div className="space-y-4">
      <div><h1 className="page-title">Administration</h1><p className="page-sub">Workflow, jurisdiction and access control are data, not code - every change is logged with the authorising order</p></div>
      <div className="flex gap-1 border-b border-light-border overflow-x-auto">{tabs.map((t) => <button key={t.k} className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 -mb-px ${tab === t.k ? "border-primary-500 text-primary-700" : "border-transparent text-light-text-muted"}`} onClick={() => setTab(t.k)}>{t.l}</button>)}</div>
      {tab === "hierarchy" && <HierarchyTab />}
      {tab === "rules" && <RulesTab />}
      {tab === "settings" && <SettingsTab />}
      {tab === "permissions" && <PermissionsTab />}
      {tab === "branches" && <BranchesTab />}
      {tab === "reassign" && <ReassignTab />}
      {tab === "sla" && <SLATab />}
      {tab === "audit" && <AuditTab />}
    </div>
  );
}

function OrderRef({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return <Field label="Authorising office order / Commissioner's order no. (recorded in the audit log)" required><input className="input" value={value} onChange={(e) => onChange(e.target.value)} placeholder="e.g. MCG/Comm/IT/2026/112 dated 10-09-2026" /></Field>;
}

function RulesTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["rules"], queryFn: admin.rules });
  const [status, setStatus] = useState("PENDING_JC");
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [ref, setRef] = useState("");
  const [err, setErr] = useState("");
  const save = useMutation({ mutationFn: () => admin.saveRules(Object.entries(pending).map(([k, allowed]) => { const [st, role, action] = k.split("|"); return { status: st, role, action, allowed }; }), ref), onSuccess: () => { qc.invalidateQueries({ queryKey: ["rules"] }); setPending({}); setRef(""); }, onError: (e) => setErr(errorMessage(e)) });
  const reset = useMutation({ mutationFn: () => admin.resetRules(ref), onSuccess: () => { qc.invalidateQueries({ queryKey: ["rules"] }); setPending({}); } });
  if (!q.data) return <Spinner />;
  const d: RulesMatrix = q.data;
  const roles = d.roles.filter((r) => !d.management_roles.includes(r));
  const is = (st: string, role: string, action: string) => { const k = `${st}|${role}|${action}`; return k in pending ? pending[k] : (d.matrix[st]?.[role] || []).includes(action); };
  const toggle = (st: string, role: string, action: string) => { const k = `${st}|${role}|${action}`; setPending({ ...pending, [k]: !is(st, role, action) }); };
  return (
    <div className="space-y-3">
      {err && <Alert kind="error">{err}</Alert>}
      <Alert kind="info">Tick which role may perform which action when a case is in the selected status. "Any status" rules apply everywhere (e.g. refer to branch, respond as branch, re-assign). ADMIN / Commissioner / Additional Commissioner always have every action. Changes take effect within 30 seconds.</Alert>
      <div className="flex flex-wrap gap-2 items-end"><Field label="Case status"><select className="input w-80" value={status} onChange={(e) => setStatus(e.target.value)}>{d.statuses.map((s) => <option key={s} value={s}>{s === "*" ? "Any status" : t(`status.${s}`, d.status_labels[s])}</option>)}</select></Field><div className="flex-1" /><span className="badge bg-secondary-100 text-secondary-600">{Object.keys(pending).length} unsaved change(s)</span></div>
      <div className="card overflow-x-auto"><table className="table text-xs"><thead><tr><th>Action</th>{roles.map((r) => <th key={r} className="text-center" title={d.role_labels[r]}>{d.role_short?.[r] || r}</th>)}</tr></thead>
        <tbody>{d.actions.map((a) => <tr key={a}><td className="font-medium whitespace-nowrap">{d.action_labels[a] || a}<div className="text-[10px] text-light-text-muted font-mono">{a}</div></td>{roles.map((r) => <td key={r} className="text-center"><input type="checkbox" checked={is(status, r, a)} onChange={() => toggle(status, r, a)} className={`${status}|${r}|${a}` in pending ? "outline outline-2 outline-secondary-500 rounded" : ""} /></td>)}</tr>)}</tbody></table></div>
      <div className="card p-4 space-y-3"><OrderRef value={ref} onChange={setRef} /><div className="flex gap-2"><button className="btn-primary" disabled={!ref || !Object.keys(pending).length || save.isPending} onClick={() => save.mutate()}><Save className="h-4 w-4" />Save rules</button><button className="btn-outline" disabled={!ref || reset.isPending} onClick={() => confirm("Reset all workflow rules to the shipped defaults?") && reset.mutate()}><RotateCcw className="h-4 w-4" />Reset to defaults</button></div></div>
    </div>
  );
}

function SettingsTab() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["settings"], queryFn: admin.settings });
  const [vals, setVals] = useState<Record<string, unknown>>({});
  const [ref, setRef] = useState("");
  const [err, setErr] = useState("");
  const save = useMutation({ mutationFn: () => admin.saveSettings(vals, ref), onSuccess: () => { qc.invalidateQueries({ queryKey: ["settings"] }); setVals({}); setRef(""); }, onError: (e) => setErr(errorMessage(e)) });
  if (!q.data) return <Spinner />;
  const groups = Array.from(new Set(q.data.map((s) => s.group)));
  const cur = (s: WorkflowSetting) => (s.key in vals ? vals[s.key] : s.value);
  return (
    <div className="space-y-3">
      {err && <Alert kind="error">{err}</Alert>}
      {groups.map((g) => <Card key={g} title={g}><div className="space-y-3">{q.data!.filter((s) => s.group === g).map((s) => <div key={s.key} className="flex items-start gap-3 border-b border-light-border pb-3 last:border-0"><div className="flex-1"><div className="font-medium text-sm">{s.label}</div><div className="text-xs text-light-text-muted">{s.description}</div><div className="text-[10px] font-mono text-light-text-muted">{s.key}</div></div>{s.value_type === "bool" ? <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!cur(s)} onChange={(e) => setVals({ ...vals, [s.key]: e.target.checked })} />{cur(s) ? "On" : "Off"}</label> : <input type="number" className="input w-28" value={String(cur(s))} onChange={(e) => setVals({ ...vals, [s.key]: e.target.value })} />}</div>)}</div></Card>)}
      <div className="card p-4 space-y-3"><OrderRef value={ref} onChange={setRef} /><button className="btn-primary" disabled={!ref || !Object.keys(vals).length || save.isPending} onClick={() => save.mutate()}><Save className="h-4 w-4" />Save settings</button></div>
    </div>
  );
}

function PermissionsTab() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["permissions"], queryFn: admin.permissions });
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [ref, setRef] = useState("");
  const [err, setErr] = useState("");
  const save = useMutation({ mutationFn: () => admin.savePermissions(Object.entries(pending).map(([k, allowed]) => { const [role, permission] = k.split("|"); return { role, permission, allowed }; }), ref), onSuccess: () => { qc.invalidateQueries({ queryKey: ["permissions"] }); setPending({}); setRef(""); }, onError: (e) => setErr(errorMessage(e)) });
  if (!q.data) return <Spinner />;
  const d: PermMatrix = q.data;
  const roles = d.roles.filter((r) => !d.management_roles.includes(r));
  const is = (role: string, p: string) => { const k = `${role}|${p}`; return k in pending ? pending[k] : (d.matrix[role] || []).includes(p); };
  const groups = Array.from(new Set(d.permissions.map((p) => p.group)));
  return (
    <div className="space-y-3">
      {err && <Alert kind="error">{err}</Alert>}
      <Alert kind="info">Role-level permissions. Individual officers can be given extra rights or have rights withdrawn from the Officers page (per-officer overrides). Workflow actions (who may issue notices, record execution ...) are on the "Workflow rules" tab.</Alert>
      <div className="card overflow-x-auto"><table className="table text-xs"><thead><tr><th>Permission</th>{roles.map((r) => <th key={r} className="text-center" title={d.role_labels[r]}>{d.role_short?.[r] || r}</th>)}</tr></thead>
        <tbody>{groups.map((g) => [<tr key={g}><td colSpan={roles.length + 1} className="bg-primary-50 text-primary-700 font-semibold">{g}</td></tr>, ...d.permissions.filter((p) => p.group === g).map((p) => <tr key={p.code}><td className="whitespace-nowrap">{p.label}<div className="text-[10px] font-mono text-light-text-muted">{p.code}</div></td>{roles.map((r) => <td key={r} className="text-center"><input type="checkbox" checked={is(r, p.code)} onChange={() => setPending({ ...pending, [`${r}|${p.code}`]: !is(r, p.code) })} className={`${r}|${p.code}` in pending ? "outline outline-2 outline-secondary-500 rounded" : ""} /></td>)}</tr>)])}</tbody></table></div>
      <div className="card p-4 space-y-3"><OrderRef value={ref} onChange={setRef} /><button className="btn-primary" disabled={!ref || !Object.keys(pending).length || save.isPending} onClick={() => save.mutate()}><Save className="h-4 w-4" />Save permissions</button></div>
    </div>
  );
}

function BranchesTab() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["branches"], queryFn: branchesApi.list });
  const [edit, setEdit] = useState<Partial<Branch> & { order_reference?: string; isNew?: boolean } | null>(null);
  const [err, setErr] = useState("");
  const save = useMutation({ mutationFn: (d: any) => (d.isNew ? branchesApi.create(d) : branchesApi.save(d)), onSuccess: () => { qc.invalidateQueries({ queryKey: ["branches"] }); setEdit(null); }, onError: (e) => setErr(errorMessage(e)) });
  return (
    <div className="space-y-3">
      {err && <Alert kind="error">{err}</Alert>}
      <div className="flex justify-end"><button className="btn-primary" onClick={() => setEdit({ isNew: true, code: "", name_en: "", default_response_days: 7, active: true })}>+ Add branch</button></div>
      <div className="grid md:grid-cols-2 gap-3">{q.data?.map((b) => <Card key={b.code} title={<span>{b.name_en} <span className="badge bg-gray-100 ml-1">{b.code}</span></span>} actions={<button className="btn-ghost text-xs" onClick={() => setEdit({ ...b })}>Edit</button>}><div className="text-sm space-y-1"><div className="text-light-text-muted">{b.name_hi}</div><div>{b.description}</div><div><b>Head:</b> {b.head_designation || "-"} · <b>Response days:</b> {b.default_response_days} · {b.active ? "active" : "inactive"}</div><div><b>Officers:</b> {b.officers.map((o) => o.name).join(", ") || <span className="text-danger-600">none assigned - create a BRANCH_OFFICER on the Officers page</span>}</div></div></Card>)}</div>
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.isNew ? "New branch" : `Branch ${edit?.code}`}>{edit && <div className="space-y-3"><div className="grid grid-cols-2 gap-2"><Field label="Code" required><input className="input font-mono" disabled={!edit.isNew} value={edit.code || ""} onChange={(e) => setEdit({ ...edit, code: e.target.value.toUpperCase().replace(/[^A-Z_]/g, "") })} /></Field><Field label="Name (English)" required><input className="input" value={edit.name_en || ""} onChange={(e) => setEdit({ ...edit, name_en: e.target.value })} /></Field><Field label="Name (Hindi)"><input className="input" value={edit.name_hi || ""} onChange={(e) => setEdit({ ...edit, name_hi: e.target.value })} /></Field><Field label="Head designation"><input className="input" value={edit.head_designation || ""} onChange={(e) => setEdit({ ...edit, head_designation: e.target.value })} /></Field><Field label="Default response days"><input type="number" className="input" value={edit.default_response_days ?? 7} onChange={(e) => setEdit({ ...edit, default_response_days: Number(e.target.value) })} /></Field><Field label="Active"><input type="checkbox" checked={!!edit.active} onChange={(e) => setEdit({ ...edit, active: e.target.checked })} /></Field></div><Field label="What this branch reports on"><textarea className="input" rows={2} value={edit.description || ""} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></Field><OrderRef value={edit.order_reference || ""} onChange={(v) => setEdit({ ...edit, order_reference: v })} /><div className="flex justify-end gap-2"><button className="btn-outline" onClick={() => setEdit(null)}>Cancel</button><button className="btn-primary" disabled={!edit.code || !edit.name_en || !edit.order_reference || save.isPending} onClick={() => save.mutate(edit)}>Save</button></div></div>}</Modal>
    </div>
  );
}

function ReassignTab() {
  const zones = useQuery({ queryKey: ["zones"], queryFn: masters.zones });
  const wards = useQuery({ queryKey: ["wards-all"], queryFn: () => masters.wards() });
  const wf = useWorkflowConfig();
  const aes = useQuery({ queryKey: ["officers", "slot", "REVIEWER"], queryFn: () => masters.officers({ slot: "REVIEWER" }) });
  const jcs = useQuery({ queryKey: ["officers", "slot", "AUTHORITY"], queryFn: () => masters.officers({ slot: "AUTHORITY" }) });
  const jes = useQuery({ queryKey: ["officers", "slot", "REPORTER"], queryFn: () => masters.officers({ slot: "REPORTER" }) });
  const [f, setF] = useState<Record<string, any>>({ only_open: true });
  const [msg, setMsg] = useState("");
  const run = useMutation({ mutationFn: () => admin.reassign(f), onSuccess: (r) => setMsg(`${r.reassigned} case(s) re-assigned`), onError: (e) => setMsg(errorMessage(e)) });
  const all = [...(aes.data || []), ...(jcs.data || []), ...(jes.data || [])];
  return (
    <div className="space-y-3">
      <Alert kind="info">Use when an officer is transferred or a ward moves to another AE/JC. Select the cases (by zone, ward or current officer) and the new officer(s). Each case gets a REASSIGNED event; the operation is logged with the transfer order.</Alert>
      <Card title="Select cases"><div className="grid md:grid-cols-4 gap-2"><Field label="Zone"><select className="input" value={f.zone || ""} onChange={(e) => setF({ ...f, zone: e.target.value || null })}><option value="">-</option>{zones.data?.map((z) => <option key={z.id} value={z.id}>Zone {z.code}</option>)}</select></Field><Field label="Ward"><select className="input" value={f.ward || ""} onChange={(e) => setF({ ...f, ward: e.target.value || null })}><option value="">-</option>{wards.data?.map((w) => <option key={w.id} value={w.id}>Ward {w.number}</option>)}</select></Field><Field label="Currently with officer"><select className="input" value={f.from_user || ""} onChange={(e) => setF({ ...f, from_user: e.target.value || null })}><option value="">-</option>{all.map((o) => <option key={o.user_id} value={o.user_id}>{o.name} ({o.role})</option>)}</select></Field><Field label="Open cases only"><input type="checkbox" checked={!!f.only_open} onChange={(e) => setF({ ...f, only_open: e.target.checked })} /></Field></div></Card>
      <Card title="Assign to"><div className="grid md:grid-cols-3 gap-2"><Field label={`New ${wf.stageLabel("REVIEWER")}`}><select className="input" value={f.assigned_ae || ""} onChange={(e) => setF({ ...f, assigned_ae: e.target.value || null })}><option value="">(unchanged)</option>{aes.data?.map((o) => <option key={o.user_id} value={o.user_id}>{o.name}</option>)}</select></Field><Field label={`New ${wf.stageLabel("AUTHORITY")}`}><select className="input" value={f.assigned_jc || ""} onChange={(e) => setF({ ...f, assigned_jc: e.target.value || null })}><option value="">(unchanged)</option>{jcs.data?.map((o) => <option key={o.user_id} value={o.user_id}>{o.name}</option>)}</select></Field><Field label={`New ${wf.stageLabel("REPORTER")} (field owner)`}><select className="input" value={f.reported_by || ""} onChange={(e) => setF({ ...f, reported_by: e.target.value || null })}><option value="">(unchanged)</option>{jes.data?.map((o) => <option key={o.user_id} value={o.user_id}>{o.name}</option>)}</select></Field></div><OrderRef value={f.order_reference || ""} onChange={(v) => setF({ ...f, order_reference: v })} /><Field label="Remarks"><input className="input" value={f.remarks || ""} onChange={(e) => setF({ ...f, remarks: e.target.value })} /></Field><div className="flex items-center gap-3 mt-2"><button className="btn-primary" disabled={!f.order_reference || !(f.zone || f.ward || f.from_user) || !(f.assigned_ae || f.assigned_jc || f.reported_by) || run.isPending} onClick={() => confirm("Re-assign the selected cases?") && run.mutate()}>Re-assign</button>{msg && <span className="text-sm">{msg}</span>}</div></Card>
    </div>
  );
}

function SLATab() {
  const qc = useQueryClient();
  const wf = useWorkflowConfig();
  const sla = useQuery({ queryKey: ["sla"], queryFn: masters.sla });
  const ots = useQuery({ queryKey: ["order-types"], queryFn: masters.orderTypes });
  const [rows, setRows] = useState<Record<number, any>>({});
  const [ot, setOt] = useState<Record<string, any>>({});
  const [msg, setMsg] = useState("");
  const api = apiClient;
  const save = useMutation({ mutationFn: async () => { for (const [id, v] of Object.entries(rows)) await api.patch(`/masters/sla/${id}/`, v); for (const [code, v] of Object.entries(ot)) await api.patch(`/masters/order-types/${code}/`, v); }, onSuccess: () => { qc.invalidateQueries({ queryKey: ["sla"] }); qc.invalidateQueries({ queryKey: ["order-types"] }); setRows({}); setOt({}); setMsg("Saved"); }, onError: (e) => setMsg(errorMessage(e)) });
  return (
    <div className="grid lg:grid-cols-2 gap-4">
      <Card title="Stage SLA (hours) and escalation"><table className="table text-xs"><thead><tr><th>Stage</th><th>Hours</th><th>Escalate to</th><th>Active</th></tr></thead><tbody>{(sla.data || []).map((s: any) => <tr key={s.id}><td>{s.label}<div className="font-mono text-[10px] text-light-text-muted">{s.stage}</div></td><td><input type="number" className="input w-24" defaultValue={s.hours} onChange={(e) => setRows({ ...rows, [s.id]: { ...(rows[s.id] || {}), hours: Number(e.target.value) } })} /></td><td><select className="input w-44" defaultValue={s.escalate_to_role} onChange={(e) => setRows({ ...rows, [s.id]: { ...(rows[s.id] || {}), escalate_to_role: e.target.value } })}><option value="">-</option>{wf.roles.filter((r) => r.active && !wf.slotRoles("REPORTER").includes(r.code) && !["JC_CLERK", "FIELD_STAFF", "BRANCH_OFFICER", "GIS_LAB", "VIEWER"].includes(r.code)).map((r) => r.code).map((r) => <option key={r}>{r}</option>)}</select></td><td><input type="checkbox" defaultChecked={s.active} onChange={(e) => setRows({ ...rows, [s.id]: { ...(rows[s.id] || {}), active: e.target.checked } })} /></td></tr>)}</tbody></table></Card>
      <Card title="Notice / order periods (days)"><table className="table text-xs"><thead><tr><th>Document</th><th>Statutory min</th><th>Default days</th><th>Active</th></tr></thead><tbody>{(ots.data || []).filter((o) => o.kind === "NOTICE" || o.kind === "ORDER").map((o) => <tr key={o.code}><td>{o.title_en}<div className="font-mono text-[10px] text-light-text-muted">{o.code}</div></td><td>{o.min_days}</td><td><input type="number" className="input w-24" min={o.min_days} defaultValue={o.default_days} onChange={(e) => setOt({ ...ot, [o.code]: { ...(ot[o.code] || {}), default_days: Number(e.target.value) } })} /></td><td><input type="checkbox" defaultChecked={o.active} onChange={(e) => setOt({ ...ot, [o.code]: { ...(ot[o.code] || {}), active: e.target.checked } })} /></td></tr>)}</tbody></table></Card>
      <div className="lg:col-span-2 flex items-center gap-3"><button className="btn-primary" disabled={(!Object.keys(rows).length && !Object.keys(ot).length) || save.isPending} onClick={() => save.mutate()}><Save className="h-4 w-4" />Save</button>{msg && <span className="text-sm">{msg}</span>}<span className="text-xs text-light-text-muted">Statutory minimum periods cannot be lowered (they are enforced at issue time).</span></div>
    </div>
  );
}

function AuditTab() {
  const [search, setSearch] = useState("");
  const q = useQuery({ queryKey: ["admin-log", search], queryFn: () => admin.auditLog(search ? { search } : {}) });
  return (
    <div className="space-y-3">
      <input className="input w-96" placeholder="Search order reference, target, remarks, actor" value={search} onChange={(e) => setSearch(e.target.value)} />
      <div className="card overflow-x-auto"><table className="table text-xs"><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Target</th><th>Order reference</th><th>Change</th></tr></thead><tbody>{(q.data || []).map((l) => <tr key={l.id}><td className="whitespace-nowrap">{fmtDateTime(l.at)}</td><td>{l.actor?.name || "-"}</td><td><span className="badge bg-primary-50 text-primary-700">{l.action}</span></td><td>{l.target_type} {l.target_id}</td><td>{l.order_reference || <span className="text-danger-600">none</span>}</td><td className="max-w-[420px]"><details><summary className="cursor-pointer text-primary-600">view</summary><pre className="text-[10px] whitespace-pre-wrap">{JSON.stringify({ before: l.before, after: l.after, remarks: l.remarks }, null, 1)}</pre></details></td></tr>)}</tbody></table></div>
    </div>
  );
}


/** Administration → Hierarchy: the chain a case travels (reporter → reviewer(s) → competent authority) and the
 *  role catalogue. Saved as data; the portal and the app relabel themselves from /masters/workflow-config/. */
function HierarchyTab() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["hierarchy"], queryFn: admin.hierarchy });
  const [stages, setStages] = useState<any[] | null>(null);
  const [roles, setRoles] = useState<any[] | null>(null);
  const [newRole, setNewRole] = useState<any | null>(null);
  const [ref, setRef] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => { if (q.data) { setStages(q.data.stages.map((s) => ({ slot: s.slot, role: s.role, label_en: s.label_en, label_hi: s.label_hi || "" }))); setRoles(q.data.roles.map((r) => ({ ...r }))); } }, [q.data]);
  const done = () => { ["hierarchy", "workflow-config", "rules", "permissions", "officers", "me"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); setRef(""); setErr(""); setMsg("Saved. Screens pick up the new names within 30 seconds (refresh the app / portal)."); };
  const save = useMutation({ mutationFn: () => admin.saveHierarchy({ stages: stages || [], roles: roles || [], order_reference: ref }), onSuccess: done, onError: (e) => setErr(errorMessage(e)) });
  const reset = useMutation({ mutationFn: () => admin.resetHierarchy(ref), onSuccess: done, onError: (e) => setErr(errorMessage(e)) });
  if (!q.data || !stages || !roles) return <Spinner />;
  const d = q.data;
  const selectable = roles.filter((r) => r.active && !d.management_roles.includes(r.code));
  const upd = (i: number, k: string, v: string) => setStages(stages.map((s, j) => (j === i ? { ...s, [k]: v } : s)));
  const pickRole = (i: number, code: string) => { const r = roles.find((x) => x.code === code); setStages(stages.map((s, j) => (j === i ? { ...s, role: code, label_en: r?.label_en || s.label_en, label_hi: r?.label_hi || s.label_hi } : s))); };
  const move = (i: number, dir: number) => { const j = i + dir; if (j <= 0 || j >= stages.length - 1) return; const n = [...stages]; [n[i], n[j]] = [n[j], n[i]]; setStages(n); };
  const remove = (i: number) => setStages(stages.filter((_, j) => j !== i));
  const addStage = () => { const used = new Set(stages.map((s) => s.role)); const cand = selectable.find((r) => !used.has(r.code)); setStages([...stages.slice(0, -1), { slot: "REVIEWER", role: cand?.code || "", label_en: cand?.label_en || "", label_hi: cand?.label_hi || "" }, stages[stages.length - 1]]); };
  const updRole = (code: string, k: string, v: unknown) => setRoles(roles.map((r) => (r.code === code ? { ...r, [k]: v } : r)));
  const preview = stages.map((s) => s.label_en || s.role).join(" → ");
  const slotCls: Record<string, string> = { REPORTER: "bg-accent-50 text-accent-700", REVIEWER: "bg-blue-50 text-blue-700", AUTHORITY: "bg-primary-50 text-primary-700" };
  return (
    <div className="space-y-3">
      {err && <Alert kind="error">{err}</Alert>}
      {msg && <Alert kind="info">{msg}</Alert>}
      <Alert kind="info">The chain a case travels: the first stage records the inspection, the middle stages review and forward (or return), the last stage is the competent authority who issues notices and orders. Rename a stage, change which role fills it, add or remove review stages - every button, status and list in the portal and the field app follows within 30 seconds. A role placed in a stage inherits the workflow rules, permissions and jurisdiction of that stage (Junior Engineer / Assistant Engineer / Joint Commissioner defaults) until you refine them on the other tabs.</Alert>
      <Card title={<span>Review chain <span className="badge bg-primary-50 text-primary-700 ml-2 font-normal">{preview}</span></span>}>
        <div className="overflow-x-auto"><table className="table text-xs"><thead><tr><th>#</th><th>Stage</th><th>Role that acts</th><th>Name shown (English)</th><th>Name shown (Hindi)</th><th></th></tr></thead>
          <tbody>{stages.map((s, i) => <tr key={i}>
            <td>{i + 1}</td>
            <td><span className={`badge ${slotCls[s.slot] || "bg-gray-100"}`}>{s.slot}</span><div className="text-[10px] text-light-text-muted">{d.slot_labels?.[s.slot]}</div></td>
            <td><select className="input" value={s.role} onChange={(e) => pickRole(i, e.target.value)}>{!selectable.some((r) => r.code === s.role) && <option value={s.role}>{s.role}</option>}{selectable.map((r) => <option key={r.code} value={r.code}>{r.label_en} ({r.code})</option>)}</select></td>
            <td><input className="input" value={s.label_en} onChange={(e) => upd(i, "label_en", e.target.value)} /></td>
            <td><input className="input" value={s.label_hi || ""} onChange={(e) => upd(i, "label_hi", e.target.value)} /></td>
            <td className="whitespace-nowrap">{s.slot === "REVIEWER" && <><button className="btn-ghost text-xs" title="Move up" onClick={() => move(i, -1)}>↑</button><button className="btn-ghost text-xs" title="Move down" onClick={() => move(i, 1)}>↓</button><button className="btn-ghost text-xs text-danger-600" onClick={() => remove(i)}>Remove</button></>}</td>
          </tr>)}</tbody></table></div>
        <div className="flex items-center gap-3 mt-2"><button className="btn-outline" onClick={addStage} disabled={!selectable.some((r) => !stages.some((s) => s.role === r.code))}>+ Add a review stage</button><span className="text-xs text-light-text-muted">No review stage = submissions go straight to the competent authority. Several review stages are visited in order (e.g. Assistant Engineer, then Executive Engineer).</span></div>
      </Card>
      <Card title="Roles - names used across the portal and the app">
        <div className="overflow-x-auto"><table className="table text-xs"><thead><tr><th>Code</th><th>Name (English)</th><th>Name (Hindi)</th><th>Short</th><th>Kind</th><th>Active</th></tr></thead>
          <tbody>{roles.map((r) => <tr key={r.code}>
            <td className="font-mono whitespace-nowrap">{r.code}{r.inherits && <div className="text-[10px] text-light-text-muted font-sans">inherits {r.inherits} defaults</div>}</td>
            <td><input className="input" value={r.label_en} onChange={(e) => updRole(r.code, "label_en", e.target.value)} /></td>
            <td><input className="input" value={r.label_hi || ""} onChange={(e) => updRole(r.code, "label_hi", e.target.value)} /></td>
            <td><input className="input w-24" value={r.short_label || ""} onChange={(e) => updRole(r.code, "short_label", e.target.value)} /></td>
            <td>{d.management_roles.includes(r.code) ? <span className="badge bg-gray-100">MANAGEMENT</span> : <select className="input" value={r.kind} onChange={(e) => updRole(r.code, "kind", e.target.value)}>{(d.kinds || ["CHAIN", "SUPPORT"]).filter((k) => k !== "MANAGEMENT").map((k) => <option key={k}>{k}</option>)}</select>}</td>
            <td className="text-center"><input type="checkbox" checked={!!r.active} disabled={d.management_roles.includes(r.code)} onChange={(e) => updRole(r.code, "active", e.target.checked)} /></td>
          </tr>)}</tbody></table></div>
        {newRole ? <div className="flex flex-wrap gap-2 items-end mt-2">
          <Field label="Code" required><input className="input font-mono w-44" value={newRole.code} onChange={(e) => setNewRole({ ...newRole, code: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "") })} placeholder="SUPERVISOR" /></Field>
          <Field label="Name (English)" required><input className="input w-56" value={newRole.label_en} onChange={(e) => setNewRole({ ...newRole, label_en: e.target.value })} placeholder="Supervisor" /></Field>
          <Field label="Name (Hindi)"><input className="input w-56" value={newRole.label_hi} onChange={(e) => setNewRole({ ...newRole, label_hi: e.target.value })} /></Field>
          <button className="btn-primary" disabled={!newRole.code || !newRole.label_en || roles.some((r) => r.code === newRole.code)} onClick={() => { setRoles([...roles, { ...newRole, short_label: newRole.code.slice(0, 8), kind: "CHAIN", active: true, builtin: false, sort_order: 200 }]); setNewRole(null); }}>Add role</button>
          <button className="btn-outline" onClick={() => setNewRole(null)}>Cancel</button>
        </div> : <button className="btn-outline mt-2" onClick={() => setNewRole({ code: "", label_en: "", label_hi: "" })}>+ New role</button>}
      </Card>
      <div className="card p-4 space-y-3"><OrderRef value={ref} onChange={setRef} /><div className="flex gap-2"><button className="btn-primary" disabled={!ref || save.isPending} onClick={() => save.mutate()}><Save className="h-4 w-4" />Save hierarchy</button><button className="btn-outline" disabled={!ref || reset.isPending} onClick={() => confirm("Reset to Junior Engineer → Assistant Engineer → Joint Commissioner and the shipped role names?") && reset.mutate()}><RotateCcw className="h-4 w-4" />Reset to default</button></div></div>
    </div>
  );
}
