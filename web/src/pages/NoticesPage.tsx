import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { masters, notices } from "@/api/endpoints";
import { Empty, Pager, Spinner } from "@/components/ui";
import { fmtDate, fmtDateTime } from "@/utils/format";

export default function NoticesPage() {
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const p = Object.fromEntries(sp.entries());
  const page = Number(p.page || 1);
  const q = useQuery({ queryKey: ["notices", p], queryFn: () => notices.list({ ...p, page, page_size: 25, ordering: "-issued_at" }) });
  const ots = useQuery({ queryKey: ["order-types"], queryFn: masters.orderTypes });
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); if (k !== "page") n.delete("page"); setSp(n); };
  return (
    <div className="space-y-4">
      <div><h1 className="page-title">Notices & Orders register</h1><p className="page-sub">Every show-cause notice, stop-work, sealing and demolition order issued by the module - digitally signed with QR verification</p></div>
      <div className="card p-3 flex flex-wrap gap-2">
        <input className="input w-64" placeholder="Notice no, case no, PID, addressee" defaultValue={p.search || ""} onKeyDown={(e) => e.key === "Enter" && set("search", (e.target as HTMLInputElement).value)} />
        <select className="input w-40" value={p.kind || ""} onChange={(e) => set("kind", e.target.value)}><option value="">All kinds</option>{["NOTICE", "ORDER", "MEMO", "REFERRAL"].map((k) => <option key={k}>{k}</option>)}</select>
        <select className="input w-80" value={p.order_type || ""} onChange={(e) => set("order_type", e.target.value)}><option value="">All types</option>{ots.data?.map((o) => <option key={o.code} value={o.code}>{o.title_en.slice(0, 70)}</option>)}</select>
        <select className="input w-44" value={p.signature_status || ""} onChange={(e) => set("signature_status", e.target.value)}><option value="">Signature: any</option>{["SIGNED", "UNSIGNED", "FAILED"].map((k) => <option key={k}>{k}</option>)}</select>
        <select className="input w-40" value={p.served_mode || ""} onChange={(e) => set("served_mode", e.target.value)}><option value="">Service: any</option>{["IN_PERSON", "AFFIXATION", "POST", "SMS", "WHATSAPP", "EMAIL", "BEAT_OF_DRUM"].map((k) => <option key={k}>{k}</option>)}</select>
      </div>
      <div className="card overflow-x-auto">{q.isLoading ? <Spinner /> : !q.data?.results.length ? <Empty /> : (
        <table className="table"><thead><tr><th>Notice no.</th><th>Type</th><th>Case / property</th><th>Addressee</th><th>Issued</th><th>Due</th><th>Service</th><th>Signature</th></tr></thead>
          <tbody>{q.data.results.map((n) => <tr key={n.id} className="hover:bg-primary-50/40 cursor-pointer" onClick={() => nav(`/cases/${n.case}?tab=notices`)}>
            <td className="font-mono text-xs font-semibold text-primary-700">{n.notice_no}<div><span className={`badge ${n.kind === "ORDER" ? "bg-danger-50 text-danger-600" : "bg-primary-50 text-primary-700"}`}>{n.kind}</span></div></td>
            <td className="max-w-[260px] text-xs">{n.order_type.title_en}<div className="text-light-text-muted">{n.order_type.statute} s.{n.order_type.section}</div></td>
            <td className="text-xs"><span className="font-mono">{n.case_no}</span></td>
            <td className="text-xs">{n.addressee_name}<div className="text-light-text-muted">{n.addressee_mobiles.join(", ")}</div></td>
            <td className="text-xs">{fmtDateTime(n.issued_at)}<div className="text-light-text-muted">{n.issued_by?.name}</div></td>
            <td className="text-xs">{n.response_due_at && <div>Reply {fmtDate(n.response_due_at)}</div>}{n.compliance_due_at && <div className="text-danger-600">Comply {fmtDate(n.compliance_due_at)}</div>}</td>
            <td className="text-xs">{n.served_at ? <span className="text-success-700">{n.served_mode} {fmtDate(n.served_at)}</span> : <span className="text-warning-600">pending</span>}<div className="text-light-text-muted">{n.dispatches.filter((d) => d.status === "SENT").length}/{n.dispatches.length} SMS</div></td>
            <td className="text-xs">{n.signature_status === "SIGNED" ? <span className="text-success-700 flex items-center gap-1"><ShieldCheck className="h-3 w-3" />signed</span> : <span className="text-danger-600">{n.signature_status}</span>}<div className="font-mono text-[10px] text-light-text-muted">{n.verification_code}</div></td>
          </tr>)}</tbody></table>)}
        {q.data && <div className="px-3 pb-3"><Pager count={q.data.count} page={page} pageSize={25} onPage={(n) => set("page", String(n))} /></div>}
      </div>
    </div>
  );
}
