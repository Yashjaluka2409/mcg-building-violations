import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { referrals } from "@/api/endpoints";
import { Empty, Pager, Spinner, StatusBadge } from "@/components/ui";
import { fmtDate, fmtDateTime } from "@/utils/format";
import { useAuth } from "@/store/auth";

/** Referrals sent to my branch (branch officers) or made by me (JC/AE). Opens the case with its full history. */
export default function BranchInboxPage() {
  const nav = useNavigate();
  const user = useAuth((s) => s.user);
  const [sp, setSp] = useSearchParams();
  const p = Object.fromEntries(sp.entries());
  const page = Number(p.page || 1);
  const q = useQuery({ queryKey: ["referrals", p], queryFn: () => referrals.list({ ...p, page, page_size: 25, ordering: "-referred_at" }) });
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); if (k !== "page") n.delete("page"); setSp(n); };
  const isBranch = user?.role === "BRANCH_OFFICER";
  return (
    <div className="space-y-4">
      <div><h1 className="page-title">{isBranch ? `${user?.branch?.name_en || "Branch"} - referrals` : "Branch referrals"}</h1><p className="page-sub">{isBranch ? "Cases sent to your branch for report. Open a case to see its complete history and respond." : "Cases you have referred to the Planning / Revenue / Legal branches"}</p></div>
      <div className="card p-3 flex flex-wrap gap-2"><select className="input w-56" value={p.status || ""} onChange={(e) => set("status", e.target.value)}><option value="">All statuses</option>{["PENDING", "RESPONDED", "CLOSED", "WITHDRAWN"].map((s) => <option key={s}>{s}</option>)}</select><input className="input w-72" placeholder="Case no, address, query" defaultValue={p.search || ""} onKeyDown={(e) => e.key === "Enter" && set("search", (e.target as HTMLInputElement).value)} /></div>
      <div className="card overflow-x-auto">{q.isLoading ? <Spinner /> : !q.data?.results.length ? <Empty /> : (
        <table className="table"><thead><tr><th>Case</th><th>Branch</th><th>Query</th><th>Referred</th><th>Due</th><th>Status</th><th>Response</th></tr></thead>
          <tbody>{q.data.results.map((r) => <tr key={r.id} className="hover:bg-primary-50/40 cursor-pointer" onClick={() => nav(`/cases/${r.case}?tab=referrals`)}>
            <td><div className="font-mono text-xs font-semibold text-primary-700">{r.case_no}</div><div className="text-xs text-light-text-muted truncate max-w-[220px]">{r.case_address}</div><StatusBadge status={r.case_status} /></td>
            <td className="text-xs">{r.branch.name_en}{r.hold_case && <div><span className="badge bg-danger-50 text-danger-600">holds final order</span></div>}</td>
            <td className="text-sm max-w-[320px]">{r.query}</td>
            <td className="text-xs">{fmtDateTime(r.referred_at)}<div className="text-light-text-muted">{r.referred_by?.name}</div></td>
            <td className={`text-xs ${r.is_overdue ? "text-danger-600 font-semibold" : ""}`}>{fmtDate(r.due_at)}{r.is_overdue && " (overdue)"}</td>
            <td><span className={`badge ${r.status === "PENDING" ? "bg-warning-50 text-warning-600" : r.status === "RESPONDED" ? "bg-success-50 text-success-700" : "bg-gray-100"}`}>{r.status}</span></td>
            <td className="text-xs max-w-[260px]">{r.response ? <>{r.recommendation && <span className="badge bg-accent-100 text-accent-700 mr-1">{r.recommendation}</span>}{r.response.slice(0, 120)}</> : "-"}</td>
          </tr>)}</tbody></table>)}
        {q.data && <div className="px-3 pb-3"><Pager count={q.data.count} page={page} pageSize={25} onPage={(n) => set("page", String(n))} /></div>}
      </div>
    </div>
  );
}
