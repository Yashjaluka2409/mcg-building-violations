import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { admin, branches as branchesApi, masters, officers } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { Alert, Empty, Field, Modal, Spinner } from "@/components/ui";
import { useAuth } from "@/store/auth";

const ROLES = ["JE", "AE", "XEN", "JC", "JC_CLERK", "FIELD_STAFF", "BRANCH_OFFICER", "ADDL_COMMISSIONER", "COMMISSIONER", "ADMIN", "VIEWER"];

/** Officer directory: role, jurisdiction (zones / wards / divisions), supervisor, branch, delegation
 *  order and per-officer permission overrides. Every save needs the authorising order reference. */
export default function OfficersPage() {
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const perms = user?.permissions || [];
  const canManage = perms.includes("OFFICERS_MANAGE");
  const [edit, setEdit] = useState<any>(null);
  const [tab, setTab] = useState<"profile" | "jurisdiction" | "permissions">("profile");
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<Record<string, string>>({});
  const q = useQuery({ queryKey: ["officers", filter], queryFn: () => officers.list(filter) });
  const zones = useQuery({ queryKey: ["zones"], queryFn: masters.zones });
  const wards = useQuery({ queryKey: ["wards-all"], queryFn: () => masters.wards() });
  const branches = useQuery({ queryKey: ["branches"], queryFn: branchesApi.list });
  const permCat = useQuery({ queryKey: ["permissions"], queryFn: admin.permissions, enabled: perms.includes("ACCESS_CONFIGURE") || canManage });
  const save = useMutation({ mutationFn: (d: any) => (d.id ? officers.update(d.id, d) : officers.create(d)), onSuccess: () => { qc.invalidateQueries({ queryKey: ["officers"] }); setEdit(null); setErr(""); }, onError: (e) => setErr(errorMessage(e)) });
  const saveOverrides = useMutation({ mutationFn: (d: { id: number; overrides: any[]; ref: string }) => admin.saveOfficerOverrides(d.id, d.overrides, d.ref), onSuccess: () => { qc.invalidateQueries({ queryKey: ["officers"] }); setErr(""); }, onError: (e) => setErr(errorMessage(e)) });
  const isJC = user?.role === "JC" && !canManage;
  const divisions = zones.data ? ["1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B"] : [];
  const wardOpts = (wards.data || []).filter((w) => !edit?.zones?.length || edit.zones.includes(w.zone));
  const [ov, setOv] = useState<Record<string, boolean | null>>({});
  useEffect(() => { if (edit?.id) { const m: Record<string, boolean | null> = {}; for (const o of edit.permission_overrides || []) m[o.permission] = o.allowed; setOv(m); } else setOv({}); }, [edit?.id]);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3"><div><h1 className="page-title">Officers, jurisdictions & access</h1><p className="page-sub">{isJC ? "Create clerk sub-logins for your office (upload of replies only)" : "Role, zones / wards / divisions, supervisor, branch and permission overrides of every user - each change is logged with the authorising order"}</p></div><div className="flex-1" /><select className="input w-44" value={filter.role || ""} onChange={(e) => setFilter({ ...filter, role: e.target.value })}><option value="">All roles</option>{ROLES.map((r) => <option key={r}>{r}</option>)}</select><select className="input w-40" value={filter.zones || ""} onChange={(e) => setFilter({ ...filter, zones: e.target.value })}><option value="">All zones</option>{zones.data?.map((z) => <option key={z.id} value={z.id}>Zone {z.code}</option>)}</select><button className="btn-primary" onClick={() => { setTab("profile"); setEdit(isJC ? { role: "JC_CLERK", active: true, zones: [], wards: [], divisions: [] } : { role: "JE", active: true, zones: [], wards: [], divisions: [] }); }}>+ {isJC ? "Add clerk" : "Add officer"}</button></div>
      {err && <Alert kind="error">{err}</Alert>}
      <div className="card overflow-x-auto">{q.isLoading ? <Spinner /> : !q.data?.results.length ? <Empty /> : <table className="table"><thead><tr><th>Name</th><th>Role</th><th>Designation</th><th>Mobile</th><th>Zones / wards / divisions</th><th>Supervisor / branch</th><th>Overrides</th><th>Active</th></tr></thead><tbody>{q.data.results.map((o: any) => <tr key={o.id} className="hover:bg-primary-50/40 cursor-pointer" onClick={() => { setTab("profile"); setEdit({ ...o, zones: o.zones, wards: o.wards, divisions: o.divisions }); }}><td className="font-medium">{o.display_name}</td><td><span className="badge bg-primary-50 text-primary-700">{o.role}</span></td><td className="text-sm">{o.designation}</td><td className="text-sm font-mono">{o.mobile}</td><td className="text-xs">Z: {o.zones?.map((z: number) => zones.data?.find((x) => x.id === z)?.code ?? z).join(", ") || "all"}<br />W: {o.wards?.map((w: number) => wards.data?.find((x) => x.id === w)?.number ?? w).join(", ") || "all"}{o.divisions?.length ? <><br />D: {o.divisions.length}</> : null}</td><td className="text-xs">{o.reports_to_name || "-"}{o.branch_name && <div className="text-accent-700">{o.branch_name}</div>}{o.delegation_order_no && <div className="text-light-text-muted">Delegation {o.delegation_order_no}</div>}</td><td className="text-xs">{o.permission_overrides?.length ? o.permission_overrides.map((x: any) => <span key={x.permission} className={`badge mr-1 ${x.allowed ? "bg-success-50 text-success-700" : "bg-danger-50 text-danger-600"}`}>{x.allowed ? "+" : "-"}{x.permission}</span>) : "-"}</td><td>{o.active ? "Yes" : "No"}</td></tr>)}</tbody></table>}</div>
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? `${edit.display_name || "Officer"} (${edit.role})` : "New officer login"} wide>{edit && <div className="space-y-3">
        {edit.id && <div className="flex gap-1 border-b border-light-border">{(["profile", "jurisdiction", "permissions"] as const).map((k) => <button key={k} className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px ${tab === k ? "border-primary-500 text-primary-700" : "border-transparent text-light-text-muted"}`} onClick={() => setTab(k)}>{k[0].toUpperCase() + k.slice(1)}</button>)}</div>}
        {(tab === "profile" || !edit.id) && <>
          {!edit.id && <div className="grid grid-cols-2 gap-2"><Field label="First name"><input className="input" value={edit.first_name || ""} onChange={(e) => setEdit({ ...edit, first_name: e.target.value })} /></Field><Field label="Last name"><input className="input" value={edit.last_name || ""} onChange={(e) => setEdit({ ...edit, last_name: e.target.value })} /></Field></div>}
          <div className="grid grid-cols-3 gap-2"><Field label="Mobile (OTP login)" required><input className="input" value={edit.mobile || ""} onChange={(e) => setEdit({ ...edit, mobile: e.target.value })} /></Field><Field label="Role" required><select className="input" value={edit.role} disabled={isJC} onChange={(e) => setEdit({ ...edit, role: e.target.value })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></Field><Field label="Designation"><input className="input" value={edit.designation || ""} onChange={(e) => setEdit({ ...edit, designation: e.target.value })} /></Field><Field label="Employee code"><input className="input" value={edit.employee_code || ""} onChange={(e) => setEdit({ ...edit, employee_code: e.target.value })} /></Field><Field label="E-mail"><input className="input" value={edit.email || ""} onChange={(e) => setEdit({ ...edit, email: e.target.value })} /></Field><Field label="Active"><label className="text-sm flex items-center gap-2 mt-2"><input type="checkbox" checked={!!edit.active} onChange={(e) => setEdit({ ...edit, active: e.target.checked })} />Login enabled</label></Field></div>
          {edit.role === "BRANCH_OFFICER" && <Field label="Branch" required><select className="input" value={edit.branch || ""} onChange={(e) => setEdit({ ...edit, branch: e.target.value || null })}><option value="">-</option>{branches.data?.map((b) => <option key={b.code} value={b.code}>{b.name_en}</option>)}</select></Field>}
          {edit.role === "JC" && <div className="grid grid-cols-2 gap-2"><Field label="Delegation order no. (s.401(2)) - printed on notices"><input className="input" value={edit.delegation_order_no || ""} onChange={(e) => setEdit({ ...edit, delegation_order_no: e.target.value })} /></Field><Field label="Delegation order date"><input type="date" className="input" value={edit.delegation_order_date || ""} onChange={(e) => setEdit({ ...edit, delegation_order_date: e.target.value })} /></Field></div>}
          {!edit.id && <JurisdictionFields edit={edit} setEdit={setEdit} zones={zones.data || []} wardOpts={wardOpts} divisions={divisions} officersList={q.data?.results || []} />}
        </>}
        {tab === "jurisdiction" && edit.id && <JurisdictionFields edit={edit} setEdit={setEdit} zones={zones.data || []} wardOpts={wardOpts} divisions={divisions} officersList={q.data?.results || []} />}
        {tab !== "permissions" && <>
          <Field label="Authorising office order / transfer order (recorded in the audit log)" required={!!edit.id}><input className="input" value={edit.order_reference || ""} onChange={(e) => setEdit({ ...edit, order_reference: e.target.value })} placeholder="e.g. Transfer order MCG/Estt/2026/88" /></Field>
          <div className="flex justify-end gap-2"><button className="btn-outline" onClick={() => setEdit(null)}>Cancel</button><button className="btn-primary" disabled={!edit.mobile || (edit.role === "BRANCH_OFFICER" && !edit.branch) || save.isPending} onClick={() => { const d = { ...edit }; for (const k of ["user", "display_name", "created_at", "permission_overrides", "effective_permissions", "reports_to_name", "branch_name"]) delete d[k]; if (!d.delegation_order_date) delete d.delegation_order_date; if (!d.reports_to) delete d.reports_to; if (!d.parent_profile) delete d.parent_profile; if (!d.branch) d.branch = null; save.mutate(d); }}>Save</button></div>
        </>}
        {tab === "permissions" && edit.id && permCat.data && <div className="space-y-3">
          <Alert kind="info">Role defaults come from Administration → Access control. Here you can grant an extra permission (+) or withdraw one (−) for this officer only. Workflow actions per status are on Administration → Workflow rules.</Alert>
          <div className="card overflow-x-auto"><table className="table text-xs"><thead><tr><th>Permission</th><th>Role default</th><th>Override</th><th>Effective</th></tr></thead><tbody>{permCat.data.permissions.map((p) => { const def = (permCat.data!.matrix[edit.role] || []).includes(p.code); const o = ov[p.code]; const eff = o == null ? def : o; return <tr key={p.code}><td>{p.label}<div className="font-mono text-[10px] text-light-text-muted">{p.code}</div></td><td>{def ? "yes" : "no"}</td><td><select className="input w-40" value={o == null ? "" : o ? "grant" : "revoke"} onChange={(e) => setOv({ ...ov, [p.code]: e.target.value === "" ? null : e.target.value === "grant" })}><option value="">(role default)</option><option value="grant">Grant (+)</option><option value="revoke">Revoke (−)</option></select></td><td className={eff ? "text-success-700 font-semibold" : "text-light-text-muted"}>{eff ? "allowed" : "no"}</td></tr>; })}</tbody></table></div>
          <Field label="Authorising order reference" required><input className="input" value={edit.order_reference || ""} onChange={(e) => setEdit({ ...edit, order_reference: e.target.value })} /></Field>
          <div className="flex justify-end gap-2"><button className="btn-outline" onClick={() => setEdit(null)}>Close</button><button className="btn-primary" disabled={!edit.order_reference || saveOverrides.isPending} onClick={() => saveOverrides.mutate({ id: edit.id, overrides: Object.entries(ov).filter(([, v]) => v != null).map(([permission, allowed]) => ({ permission, allowed: !!allowed })), ref: edit.order_reference })}>Save overrides</button></div>
        </div>}
      </div>}</Modal>
    </div>
  );
}

function JurisdictionFields({ edit, setEdit, zones, wardOpts, divisions, officersList }: any) {
  const toggle = (k: string, id: number | string) => setEdit({ ...edit, [k]: (edit[k] || []).includes(id) ? edit[k].filter((x: any) => x !== id) : [...(edit[k] || []), id] });
  const supervisors = officersList.filter((o: any) => ["AE", "XEN", "JC", "ADDL_COMMISSIONER", "COMMISSIONER"].includes(o.role) && o.id !== edit.id);
  return (
    <div className="space-y-3">
      <Field label="Zones (leave empty for all)"><div className="flex flex-wrap gap-3">{zones.map((z: any) => <label key={z.id} className="text-sm flex items-center gap-1"><input type="checkbox" checked={edit.zones?.includes(z.id)} onChange={() => toggle("zones", z.id)} />Zone {z.code}</label>)}</div></Field>
      <Field label="Wards (leave empty for all wards of the zones)"><div className="flex flex-wrap gap-2 max-h-28 overflow-y-auto">{wardOpts.map((w: any) => <label key={w.id} className={`text-xs px-2 py-1 rounded border cursor-pointer ${edit.wards?.includes(w.id) ? "bg-primary-50 border-primary-300 text-primary-700" : "border-light-border"}`}><input type="checkbox" className="hidden" checked={edit.wards?.includes(w.id)} onChange={() => toggle("wards", w.id)} />W{w.number}</label>)}</div></Field>
      <Field label="Engineering divisions"><div className="flex flex-wrap gap-3">{divisions.map((d: string, i: number) => <label key={d} className="text-sm flex items-center gap-1"><input type="checkbox" checked={edit.divisions?.includes(i + 1)} onChange={() => toggle("divisions", i + 1)} />{d}</label>)}</div></Field>
      <Field label="Reports to (supervisor)"><select className="input" value={edit.reports_to || ""} onChange={(e) => setEdit({ ...edit, reports_to: e.target.value ? Number(e.target.value) : null })}><option value="">-</option>{supervisors.map((o: any) => <option key={o.id} value={o.id}>{o.display_name} ({o.role})</option>)}</select></Field>
    </div>
  );
}
