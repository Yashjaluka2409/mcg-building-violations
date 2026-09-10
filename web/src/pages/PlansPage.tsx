import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Upload } from "lucide-react";
import { useState } from "react";
import { masters, plans } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import type { Media, SanctionedPlan } from "@/api/types";
import MediaGallery from "@/components/MediaGallery";
import Uploader from "@/components/Uploader";
import { Alert, Empty, Field, Modal, Pager, Spinner } from "@/components/ui";
import { fmtDate } from "@/utils/format";
import { useAuth } from "@/store/auth";

const FIELDS: [keyof SanctionedPlan, string, string?][] = [["plan_no", "Sanction / BR-I number"], ["pid", "PID"], ["owner_name", "Owner"], ["owner_mobile", "Owner mobile"], ["address", "Address"], ["land_use", "Land use"], ["building_type", "Building type"], ["sanctioned_on", "Sanctioned on", "date"], ["valid_till", "Valid till", "date"], ["sanction_mode", "Mode (regular / self-certification / deemed)"], ["permitted_floors", "Permitted floors (e.g. S+3)"], ["permitted_ground_coverage_pct", "Permitted ground coverage %"], ["permitted_far", "Permitted FAR"], ["permitted_height_m", "Permitted height (m)"], ["plot_area_sqm", "Plot area (sq m)"], ["licence_no", "Licence no. (colony / other)"], ["licence_holder", "Licence holder"], ["licence_date", "Licence date", "date"], ["licence_valid_till", "Licence valid till", "date"], ["licence_authority", "Licence authority (DTCP / MCG / HSVP)"], ["colony_name", "Colony"], ["architect_name", "Architect"], ["architect_registration_no", "Architect regn. no."], ["occupation_certificate_no", "OC number"], ["occupation_certificate_on", "OC date", "date"], ["latitude", "Latitude"], ["longitude", "Longitude"], ["status", "Status (VALID / EXPIRED / REVOKED / COMPLETED)"]];

export default function PlansPage() {
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const [p, setP] = useState<Record<string, any>>({ page: 1 });
  const [edit, setEdit] = useState<Partial<SanctionedPlan> | null>(null);
  const [docs, setDocs] = useState<Media[]>([]);
  const [bulk, setBulk] = useState<any>(null);
  const [err, setErr] = useState("");
  const wards = useQuery({ queryKey: ["wards-all"], queryFn: () => masters.wards() });
  const q = useQuery({ queryKey: ["plans", p], queryFn: () => plans.list({ ...p, page_size: 25 }) });
  const save = useMutation({ mutationFn: (d: Partial<SanctionedPlan>) => (d.id ? plans.update(d.id, d) : plans.create(d)), onSuccess: () => { qc.invalidateQueries({ queryKey: ["plans"] }); setEdit(null); setDocs([]); }, onError: (e) => setErr(errorMessage(e)) });
  const upload = useMutation({ mutationFn: (f: File) => { const fd = new FormData(); fd.append("file", f); return plans.bulkUpload(fd); }, onSuccess: (r) => { setBulk(r); qc.invalidateQueries({ queryKey: ["plans"] }); }, onError: (e) => setErr(errorMessage(e)) });
  const canEdit = ["JE", "AE", "JC", "XEN", "ADMIN", "COMMISSIONER", "ADDL_COMMISSIONER"].includes(user?.role || "");
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3"><div><h1 className="page-title">Sanctioned building plans & licences</h1><p className="page-sub">Register of plots with sanctioned building plans / licences; auto-linked to inspections by PID</p></div><div className="flex-1" />
        {canEdit && <><a className="btn-outline" href={plans.templateUrl} onClick={async (e) => { e.preventDefault(); const { api } = await import("@/api/client"); const r = await api.get("/sanctioned-plans/template/", { responseType: "blob" }); const u = URL.createObjectURL(r.data); const a = document.createElement("a"); a.href = u; a.download = "sanctioned_plans_template.csv"; a.click(); }}><Download className="h-4 w-4" />CSV template</a>
          <label className="btn-outline cursor-pointer"><Upload className="h-4 w-4" />Bulk upload (CSV/XLSX)<input type="file" accept=".csv,.xlsx" className="hidden" onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} /></label>
          <button className="btn-primary" onClick={() => setEdit({ status: "VALID" })}>+ Add plan</button></>}
      </div>
      {err && <Alert kind="error">{err}</Alert>}
      {bulk && <Alert kind={bulk.errors.length ? "warning" : "success"}>Bulk upload: {bulk.created} created, {bulk.updated} updated{bulk.errors.length ? `, ${bulk.errors.length} errors: ${bulk.errors.slice(0, 5).map((e: any) => `row ${e.row}: ${e.error}`).join("; ")}` : ""}</Alert>}
      <div className="card p-3 flex flex-wrap gap-2"><input className="input w-72" placeholder="Plan no, PID, owner, licence, colony" onKeyDown={(e) => e.key === "Enter" && setP({ ...p, search: (e.target as HTMLInputElement).value, page: 1 })} /><select className="input w-40" value={p.ward || ""} onChange={(e) => setP({ ...p, ward: e.target.value, page: 1 })}><option value="">All wards</option>{wards.data?.map((w) => <option key={w.id} value={w.id}>Ward {w.number}</option>)}</select><select className="input w-40" value={p.status || ""} onChange={(e) => setP({ ...p, status: e.target.value, page: 1 })}><option value="">Any status</option>{["VALID", "EXPIRED", "REVOKED", "COMPLETED"].map((s) => <option key={s}>{s}</option>)}</select></div>
      <div className="card overflow-x-auto">{q.isLoading ? <Spinner /> : !q.data?.results.length ? <Empty /> : (
        <table className="table"><thead><tr><th>Plan no.</th><th>PID / address</th><th>Owner</th><th>Sanction</th><th>Permitted</th><th>Licence</th><th>Status</th></tr></thead>
          <tbody>{q.data.results.map((r) => <tr key={r.id} className="hover:bg-primary-50/40 cursor-pointer" onClick={() => canEdit && setEdit(r)}>
            <td className="font-mono text-xs font-semibold text-primary-700">{r.plan_no}</td><td className="text-xs max-w-[260px]">{r.pid && <div className="font-mono">{r.pid}</div>}<div className="truncate">{r.address}</div><div className="text-light-text-muted">Ward {r.ward_number ?? "-"}</div></td><td className="text-xs">{r.owner_name}<div className="text-light-text-muted">{r.owner_mobile}</div></td>
            <td className="text-xs">{fmtDate(r.sanctioned_on)} → {fmtDate(r.valid_till)}<div className="text-light-text-muted">{r.sanction_mode} · {r.land_use}</div></td><td className="text-xs">{r.permitted_floors} · {r.permitted_ground_coverage_pct}% · FAR {r.permitted_far} · {r.permitted_height_m} m</td>
            <td className="text-xs">{r.licence_no || "-"}<div className="text-light-text-muted">{r.licence_holder} {r.licence_authority && `(${r.licence_authority})`}</div></td><td><span className={`badge ${r.status === "VALID" ? "bg-success-50 text-success-700" : "bg-gray-100"}`}>{r.status}</span></td></tr>)}</tbody></table>)}
        {q.data && <div className="px-3 pb-3"><Pager count={q.data.count} page={p.page} pageSize={25} onPage={(n) => setP({ ...p, page: n })} /></div>}</div>
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? `Sanctioned plan ${edit.plan_no}` : "Add sanctioned plan / licence"} wide>
        {edit && <div className="space-y-3"><div className="grid md:grid-cols-3 gap-2">{FIELDS.map(([k, label, type]) => <Field key={String(k)} label={label}><input type={type || "text"} className="input" value={(edit as any)[k] ?? ""} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} /></Field>)}
          <Field label="Ward"><select className="input" value={edit.ward ?? ""} onChange={(e) => setEdit({ ...edit, ward: e.target.value ? Number(e.target.value) : null })}><option value="">-</option>{wards.data?.map((w) => <option key={w.id} value={w.id}>Ward {w.number}</option>)}</select></Field></div>
          <Field label="Remarks"><textarea className="input" rows={2} value={edit.remarks || ""} onChange={(e) => setEdit({ ...edit, remarks: e.target.value })} /></Field>
          {edit.id && <><Field label="Sanction letter / plan / licence documents"><Uploader kind="SANCTION_DOC" onUploaded={(m) => setDocs((s) => [...s, m])} accept=".pdf,image/*" label="Upload sanction / licence documents" /></Field><MediaGallery items={[...(edit.documents || []), ...docs]} /></>}
          <div className="flex justify-end gap-2"><button className="btn-outline" onClick={() => setEdit(null)}>Cancel</button><button className="btn-primary" disabled={!edit.plan_no || !edit.address || !edit.owner_name || !edit.sanctioned_on || save.isPending} onClick={() => { const d: any = { ...edit }; for (const k of Object.keys(d)) if (d[k] === "" || d[k] === null) delete d[k]; delete d.documents; delete d.ward_number; save.mutate(d); }}>Save</button></div></div>}
      </Modal>
    </div>
  );
}
