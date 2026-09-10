import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { masters } from "@/api/endpoints";
import { Card, SeverityBadge, Spinner } from "@/components/ui";
import { inr } from "@/utils/format";

export default function LegalPage() {
  const [tab, setTab] = useState<"violations" | "sections" | "orders">("violations");
  const [q, setQ] = useState("");
  const [statute, setStatute] = useState("");
  const vt = useQuery({ queryKey: ["vtypes"], queryFn: masters.violationTypes });
  const secs = useQuery({ queryKey: ["sections"], queryFn: () => masters.legalSections() });
  const stats = useQuery({ queryKey: ["statutes"], queryFn: masters.statutes });
  const ots = useQuery({ queryKey: ["order-types"], queryFn: masters.orderTypes });
  const secIndex = useMemo(() => new Map((secs.data || []).map((s) => [`${s.statute}|${s.section}`, s])), [secs.data]);
  const match = (s: string) => !q || s.toLowerCase().includes(q.toLowerCase());
  return (
    <div className="space-y-4">
      <div><h1 className="page-title">Legal catalogue</h1><p className="page-sub">Violation types, statutory provisions and notice/order types built into the workflow (source of truth: shared/legal/*.json)</p></div>
      <div className="flex flex-wrap gap-2 items-center"><div className="flex gap-1 border-b border-light-border">{(["violations", "sections", "orders"] as const).map((k) => <button key={k} className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${tab === k ? "border-primary-500 text-primary-700" : "border-transparent text-light-text-muted"}`} onClick={() => setTab(k)}>{k === "violations" ? `Violation types (${vt.data?.length ?? 0})` : k === "sections" ? `Statutory sections (${secs.data?.length ?? 0})` : `Notice & order types (${ots.data?.length ?? 0})`}</button>)}</div><div className="flex-1" /><input className="input w-72" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />{tab === "sections" && <select className="input w-72" value={statute} onChange={(e) => setStatute(e.target.value)}><option value="">All statutes</option>{stats.data?.map((s) => <option key={s.code} value={s.code}>{s.title} ({s.sections})</option>)}</select>}</div>
      {tab === "violations" && (vt.isLoading ? <Spinner /> : <div className="grid md:grid-cols-2 gap-3">{vt.data?.filter((v) => match(`${v.code} ${v.title_en} ${v.title_hi} ${v.contravention_of}`)).map((v) => <Card key={v.code} title={<span><span className="font-mono text-xs text-primary-600 mr-2">{v.code}</span>{v.title_en}</span>} actions={<SeverityBadge s={v.severity} />}>
        <div className="text-sm space-y-2"><div className="text-light-text-muted">{v.title_hi}</div><p>{v.description}</p><div className="text-xs"><b>Contravention of:</b> {v.contravention_of}</div>
          <div className="flex flex-wrap gap-1 text-xs">{v.legal_basis.map((b) => { const s = secIndex.get(`${b.statute}|${b.section}`); return <span key={b.statute + b.section} className="badge bg-gray-100" title={s?.heading}>{b.statute} s.{b.section}</span>; })}</div>
          <div className="text-xs grid grid-cols-2 gap-1"><div><b>Action path:</b> {v.action_path}</div><div><b>Compoundable:</b> {v.compoundable}</div><div><b>SCN reply:</b> {v.scn_response_days_default} d</div><div><b>Order compliance:</b> {v.order_compliance_days_default} d (min {v.statutory_minimum_days})</div><div><b>Fine (Third Sch.):</b> {v.schedule_fine_inr ? inr(v.schedule_fine_inr) : "-"}{v.schedule_daily_fine_inr ? ` + ${inr(v.schedule_daily_fine_inr)}/day` : ""}</div><div><b>Appeal:</b> {v.appeal}</div></div>
          <div className="text-xs"><b>Orders available:</b> {v.orders_available.join(", ")}</div><div className="text-xs"><b>Evidence:</b> {v.evidence_checklist.join("; ")}</div>{v.notes && <div className="text-xs text-light-text-muted">{v.notes}</div>}</div></Card>)}</div>)}
      {tab === "sections" && (secs.isLoading ? <Spinner /> : <div className="space-y-2">{secs.data?.filter((s) => (!statute || s.statute === statute) && match(`${s.section} ${s.heading} ${s.text}`)).map((s) => <Card key={s.id} title={<span><span className="badge bg-primary-50 text-primary-700 mr-2">{s.statute}</span>s.{s.section} - {s.heading}</span>} actions={<span className="flex gap-1">{s.verify && <span className="badge bg-warning-50 text-warning-600">verify against Gazette</span>}<span className="badge bg-gray-100">{s.kind}</span></span>}><p className="text-sm whitespace-pre-wrap">{s.text}</p>{(s.schedule_fine_inr || s.notes) && <div className="text-xs text-light-text-muted mt-2">{s.schedule_fine_inr && <span>Fine {inr(s.schedule_fine_inr)}{s.schedule_daily_fine_inr ? ` + ${inr(s.schedule_daily_fine_inr)}/day` : ""}. </span>}{s.notes}</div>}</Card>)}</div>)}
      {tab === "orders" && (ots.isLoading ? <Spinner /> : <div className="card overflow-x-auto"><table className="table"><thead><tr><th>Code</th><th>Title</th><th>Statute</th><th>Kind</th><th>Min days</th><th>Default days</th><th>Appeal</th><th>Template</th></tr></thead><tbody>{ots.data?.filter((o) => match(`${o.code} ${o.title_en} ${o.title_hi}`)).map((o) => <tr key={o.code}><td className="font-mono text-xs">{o.code}</td><td className="text-sm">{o.title_en}<div className="text-xs text-light-text-muted">{o.title_hi}</div></td><td className="text-xs">{o.statute} s.{o.section}</td><td><span className="badge bg-gray-100">{o.kind}</span></td><td>{o.min_days}</td><td>{o.default_days}</td><td className="text-xs">{o.appeal_to}{o.appeal_days ? ` (${o.appeal_days} d)` : ""}</td><td className="font-mono text-xs">{o.template}</td></tr>)}</tbody></table></div>)}
    </div>
  );
}
