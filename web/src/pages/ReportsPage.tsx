import { useQuery } from "@tanstack/react-query";
import { FileSpreadsheet, FileText } from "lucide-react";
import { useState } from "react";
import { masters, reports } from "@/api/endpoints";
import { api } from "@/api/client";
import { Card, Empty, Spinner } from "@/components/ui";

const DESC: Record<string, string> = { "case-register": "Every case with all key dates (inspection → closure)", "notice-register": "All notices/orders with service and signature status", "order-register": "Final demolition / sealing / eviction orders", "execution-register": "Demolitions and sealings carried out, cost and recovery", pendency: "Open cases by officer with SLA position", "govt-land": "Cases on MCG / Government land with parcel details", "sla-breach": "Stage-wise SLA breaches and escalations", "sanctioned-plans": "Sanctioned plans / licences register with linked cases" };

export default function ReportsPage() {
  const [name, setName] = useState("case-register");
  const [f, setF] = useState<Record<string, string>>({});
  const list = useQuery({ queryKey: ["reports"], queryFn: reports.list });
  const zones = useQuery({ queryKey: ["zones"], queryFn: masters.zones });
  const q = useQuery({ queryKey: ["report", name, f], queryFn: () => reports.run(name, f) });
  const dl = async (fmt: "csv" | "xlsx") => { const r = await api.get(`/reports/${name}/`, { params: { ...f, export: fmt }, responseType: "blob" }); const u = URL.createObjectURL(r.data); const a = document.createElement("a"); a.href = u; a.download = `${name}.${fmt}`; a.click(); };
  return (
    <div className="space-y-4">
      <div><h1 className="page-title">Reports</h1><p className="page-sub">Registers for the Commissioner's review, court replies and RTI - export to Excel or CSV</p></div>
      <div className="grid lg:grid-cols-4 gap-4">
        <Card title="Registers"><div className="space-y-1">{list.data?.map((r) => <button key={r.name} className={`block w-full text-left rounded-lg px-3 py-2 text-sm ${name === r.name ? "bg-primary-50 text-primary-700 font-medium" : "hover:bg-gray-50"}`} onClick={() => setName(r.name)}>{r.title}<div className="text-xs text-light-text-muted font-normal">{DESC[r.name]}</div></button>)}</div></Card>
        <div className="lg:col-span-3 space-y-3">
          <div className="card p-3 flex flex-wrap gap-2 items-center"><select className="input w-40" value={f.zone || ""} onChange={(e) => setF({ ...f, zone: e.target.value })}><option value="">All zones</option>{zones.data?.map((z) => <option key={z.id} value={z.id}>Zone {z.code}</option>)}</select><input type="date" className="input w-40" value={f.from || ""} onChange={(e) => setF({ ...f, from: e.target.value })} /><input type="date" className="input w-40" value={f.to || ""} onChange={(e) => setF({ ...f, to: e.target.value })} /><select className="input w-40" value={f.land_type || ""} onChange={(e) => setF({ ...f, land_type: e.target.value })}><option value="">Any land</option>{["GOVT_MCG", "GOVT_STATE", "PRIVATE"].map((l) => <option key={l}>{l}</option>)}</select><div className="flex-1" /><button className="btn-outline" onClick={() => dl("csv")}><FileText className="h-4 w-4" />CSV</button><button className="btn-primary" onClick={() => dl("xlsx")}><FileSpreadsheet className="h-4 w-4" />Excel</button></div>
          <div className="card overflow-x-auto">{q.isLoading ? <Spinner /> : !q.data?.rows.length ? <Empty /> : <table className="table text-xs"><thead><tr>{q.data.columns.map((c) => <th key={c}>{c.replace(/_/g, " ")}</th>)}</tr></thead><tbody>{q.data.rows.slice(0, 300).map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j} className="whitespace-nowrap">{v == null ? "" : typeof v === "boolean" ? (v ? "Yes" : "No") : String(v).replace("T", " ").slice(0, 40)}</td>)}</tr>)}</tbody></table>}{q.data && <div className="px-3 py-2 text-xs text-light-text-muted">{q.data.count} rows{q.data.count > 300 && " (first 300 shown - export for full data)"}</div>}</div>
        </div>
      </div>
    </div>
  );
}
