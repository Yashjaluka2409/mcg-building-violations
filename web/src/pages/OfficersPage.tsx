import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { masters, officers } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { Alert, Empty, Field, Modal, Spinner } from "@/components/ui";
import { useAuth } from "@/store/auth";

const ROLES = ["JE", "AE", "XEN", "JC", "JC_CLERK", "FIELD_STAFF", "ADDL_COMMISSIONER", "COMMISSIONER", "ADMIN", "VIEWER"];

export default function OfficersPage() {
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const [edit, setEdit] = useState<any>(null);
  const [err, setErr] = useState("");
  const q = useQuery({ queryKey: ["officers"], queryFn: () => officers.list() });
  const zones = useQuery({ queryKey: ["zones"], queryFn: masters.zones });
  const save = useMutation({ mutationFn: (d: any) => (d.id ? officers.update(d.id, d) : officers.create(d)), onSuccess: () => { qc.invalidateQueries({ queryKey: ["officers"] }); setEdit(null); setErr(""); }, onError: (e) => setErr(errorMessage(e)) });
  const isJC = user?.role === "JC";
  return (
    <div className="space-y-4">
      <div className="flex items-end gap-3"><div><h1 className="page-title">Officers & logins</h1><p className="page-sub">{isJC ? "Create clerk sub-logins for your office (upload of replies only)" : "Role, jurisdiction and delegation of every user of the module"}</p></div><div className="flex-1" /><button className="btn-primary" onClick={() => setEdit(isJC ? { role: "JC_CLERK", active: true, zones: [] } : { role: "JE", active: true, zones: [] })}>+ {isJC ? "Add clerk" : "Add officer"}</button></div>
      {err && <Alert kind="error">{err}</Alert>}
      <div className="card overflow-x-auto">{q.isLoading ? <Spinner /> : !q.data?.results.length ? <Empty /> : <table className="table"><thead><tr><th>Name</th><th>Role</th><th>Designation</th><th>Mobile</th><th>Zones</th><th>Delegation order</th><th>Active</th></tr></thead><tbody>{q.data.results.map((o: any) => <tr key={o.id} className="hover:bg-primary-50/40 cursor-pointer" onClick={() => setEdit({ ...o, zones: o.zones })}><td className="font-medium">{o.display_name}</td><td><span className="badge bg-primary-50 text-primary-700">{o.role}</span></td><td className="text-sm">{o.designation}</td><td className="text-sm font-mono">{o.mobile}</td><td className="text-xs">{o.zones?.map((z: number) => `Z${zones.data?.find((x) => x.id === z)?.code ?? z}`).join(", ") || "all"}</td><td className="text-xs">{o.delegation_order_no}</td><td>{o.active ? "Yes" : "No"}</td></tr>)}</tbody></table>}</div>
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? "Edit officer" : "New officer login"}>{edit && <div className="space-y-3">
        {!edit.id && <div className="grid grid-cols-2 gap-2"><Field label="First name"><input className="input" value={edit.first_name || ""} onChange={(e) => setEdit({ ...edit, first_name: e.target.value })} /></Field><Field label="Last name"><input className="input" value={edit.last_name || ""} onChange={(e) => setEdit({ ...edit, last_name: e.target.value })} /></Field></div>}
        <div className="grid grid-cols-2 gap-2"><Field label="Mobile (OTP login)" required><input className="input" value={edit.mobile || ""} onChange={(e) => setEdit({ ...edit, mobile: e.target.value })} /></Field><Field label="Role" required><select className="input" value={edit.role} disabled={isJC} onChange={(e) => setEdit({ ...edit, role: e.target.value })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></Field><Field label="Designation"><input className="input" value={edit.designation || ""} onChange={(e) => setEdit({ ...edit, designation: e.target.value })} /></Field><Field label="Employee code"><input className="input" value={edit.employee_code || ""} onChange={(e) => setEdit({ ...edit, employee_code: e.target.value })} /></Field><Field label="E-mail"><input className="input" value={edit.email || ""} onChange={(e) => setEdit({ ...edit, email: e.target.value })} /></Field></div>
        <Field label="Zones (leave empty for all)"><div className="flex gap-3">{zones.data?.map((z) => <label key={z.id} className="text-sm flex items-center gap-1"><input type="checkbox" checked={edit.zones?.includes(z.id)} onChange={(e) => setEdit({ ...edit, zones: e.target.checked ? [...(edit.zones || []), z.id] : edit.zones.filter((x: number) => x !== z.id) })} />Zone {z.code}</label>)}</div></Field>
        {edit.role === "JC" && <div className="grid grid-cols-2 gap-2"><Field label="Delegation order no. (s.401(2)) - printed on notices"><input className="input" value={edit.delegation_order_no || ""} onChange={(e) => setEdit({ ...edit, delegation_order_no: e.target.value })} /></Field><Field label="Delegation order date"><input type="date" className="input" value={edit.delegation_order_date || ""} onChange={(e) => setEdit({ ...edit, delegation_order_date: e.target.value })} /></Field></div>}
        <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={!!edit.active} onChange={(e) => setEdit({ ...edit, active: e.target.checked })} />Active</label>
        <div className="flex justify-end gap-2"><button className="btn-outline" onClick={() => setEdit(null)}>Cancel</button><button className="btn-primary" disabled={!edit.mobile || save.isPending} onClick={() => { const d = { ...edit }; delete d.user; delete d.display_name; delete d.created_at; delete d.wards; delete d.divisions; if (!d.delegation_order_date) delete d.delegation_order_date; if (!d.reports_to) delete d.reports_to; if (!d.parent_profile) delete d.parent_profile; save.mutate(d); }}>Save</button></div></div>}</Modal>
    </div>
  );
}
