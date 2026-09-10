import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Gavel, Lock, OctagonPause, Search, Share2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { cases, masters } from "@/api/endpoints";
import { Empty, LandBadge, Pager, Spinner, StatusBadge } from "@/components/ui";
import { ago, fmtDate } from "@/utils/format";
import { useAuth } from "@/store/auth";

const STATUSES = ["DRAFT", "PENDING_AE", "RETURNED_TO_JE", "PENDING_JC", "SCN_ISSUED", "SCN_SERVED", "RESPONSE_PENDING_AE", "RESPONSE_PENDING_JC", "NO_RESPONSE", "HEARING_SCHEDULED", "ORDER_ISSUED", "ORDER_SERVED", "APPEAL_STAY", "EXECUTION_DUE", "COMPLIED", "EXECUTED", "CLOSED", "DROPPED", "REGULARISED"];

export default function CasesPage({ inbox }: { inbox?: boolean }) {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const user = useAuth((s) => s.user);
  const p = Object.fromEntries(sp.entries());
  const page = Number(p.page || 1);
  const params: Record<string, unknown> = { ...p, page, page_size: 25, ordering: p.ordering || "-updated_at" };
  if (inbox) params.inbox = 1;
  const zones = useQuery({ queryKey: ["zones"], queryFn: masters.zones });
  const wards = useQuery({ queryKey: ["wards", p.zone], queryFn: () => masters.wards(p.zone ? Number(p.zone) : undefined) });
  const q = useQuery({ queryKey: ["cases", params], queryFn: () => cases.list(params) });
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); if (k !== "page") n.delete("page"); setSp(n); };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div><h1 className="page-title">{inbox ? t("nav.inbox") : t("nav.cases")}</h1><p className="page-sub">{inbox ? `Cases waiting for action by ${user?.role}` : "All violation cases in your jurisdiction"}</p></div>
        <div className="flex-1" />
        {["JE", "AE", "FIELD_STAFF", "ADMIN"].includes(user?.role || "") && <button className="btn-primary" onClick={() => nav("/cases/new")}>+ {t("nav.new_case")}</button>}
      </div>
      <div className="card p-3 flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[220px]"><Search className="h-4 w-4 absolute left-3 top-2.5 text-light-text-muted" /><input className="input pl-9" placeholder="Case no, PID, address, owner..." defaultValue={p.search || ""} onKeyDown={(e) => e.key === "Enter" && set("search", (e.target as HTMLInputElement).value)} /></div>
        <select className="input w-44" value={p.status || ""} onChange={(e) => set("status", e.target.value)}><option value="">{t("common.all")} statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}</select>
        <select className="input w-36" value={p.zone || ""} onChange={(e) => { set("zone", e.target.value); set("ward", ""); }}><option value="">{t("common.zone")}</option>{zones.data?.map((z) => <option key={z.id} value={z.id}>Zone {z.code}</option>)}</select>
        <select className="input w-36" value={p.ward || ""} onChange={(e) => set("ward", e.target.value)}><option value="">{t("common.ward")}</option>{wards.data?.map((w) => <option key={w.id} value={w.id}>Ward {w.number}</option>)}</select>
        <select className="input w-40" value={p.land_type || ""} onChange={(e) => set("land_type", e.target.value)}><option value="">Land type</option>{["GOVT_MCG", "GOVT_STATE", "PRIVATE", "UNKNOWN"].map((l) => <option key={l} value={l}>{t(`land.${l}`)}</option>)}</select>
        <select className="input w-44" value={p.litigation_status || ""} onChange={(e) => set("litigation_status", e.target.value)}><option value="">Litigation: any</option><option value="NONE">None</option><option value="APPEAL_PENDING">Appeal pending</option><option value="STAYED">Stayed</option><option value="DECIDED">Decided</option></select>
        <label className="text-sm flex items-center gap-1"><input type="checkbox" checked={p.overdue === "1"} onChange={(e) => set("overdue", e.target.checked ? "1" : "")} /> Overdue only</label>
        <label className="text-sm flex items-center gap-1"><input type="checkbox" checked={p.mine === "1"} onChange={(e) => set("mine", e.target.checked ? "1" : "")} /> Mine</label>
        <button className="btn-outline" onClick={() => setSp(new URLSearchParams())}>{t("common.reset")}</button>
      </div>
      <div className="card overflow-x-auto">
        {q.isLoading ? <Spinner /> : !q.data?.results.length ? <Empty /> : (
          <table className="table">
            <thead><tr><th>Case</th><th>Property</th><th>Violation</th><th>Land</th><th>Status</th><th>With</th><th>Due</th><th>Updated</th></tr></thead>
            <tbody>{q.data.results.map((c) => (
              <tr key={c.id} className="hover:bg-primary-50/40 cursor-pointer" onClick={() => nav(`/cases/${c.id}`)}>
                <td><div className="font-mono text-xs font-semibold text-primary-700">{c.case_no}</div><div className="text-xs text-light-text-muted">Z{c.zone_code ?? "-"} / W{c.ward_number ?? "-"} · {c.priority}</div><div className="flex gap-1 mt-1">{c.stop_work_issued && <span title="Stop-work order"><OctagonPause className="h-4 w-4 text-danger-500" /></span>}{c.sealed && <span title="Sealed"><Lock className="h-4 w-4 text-warning-600" /></span>}{c.sla_breached && <span title="SLA breached"><AlertTriangle className="h-4 w-4 text-danger-600" /></span>}{c.litigation_status === "STAYED" && <span title={`Stayed by ${c.litigation_authority}${c.stay_until ? " till " + fmtDate(c.stay_until) : ""}`}><Gavel className="h-4 w-4 text-slate-700" /></span>}{c.pending_referrals?.length > 0 && <span title={`Awaiting ${c.pending_referrals.join(", ")}`}><Share2 className="h-4 w-4 text-accent-600" /></span>}</div>{c.litigation_status === "STAYED" && <div className="text-[10px] text-slate-700 font-semibold">STAY · {c.litigation_authority?.replace(/_/g, " ")}{c.stay_until ? ` till ${fmtDate(c.stay_until)}` : ""}</div>}{c.pending_referrals?.length > 0 && <div className="text-[10px] text-accent-700">with {c.pending_referrals.join(", ")}</div>}</td>
                <td className="max-w-[260px]"><div className="truncate font-medium">{c.address_line}</div><div className="text-xs text-light-text-muted">{c.pid ? `PID ${c.pid} · ` : ""}{c.owner_name || "-"}</div></td>
                <td className="max-w-[240px]"><div className="text-xs"><span className="font-mono text-primary-600">{c.primary_violation?.code}</span> {c.primary_violation?.title_en}</div>{c.violation_codes.length > 1 && <div className="text-[11px] text-light-text-muted">+{c.violation_codes.length - 1} more</div>}</td>
                <td><LandBadge land={c.land_type} /></td>
                <td><StatusBadge status={c.status} /><div className="text-[11px] text-light-text-muted mt-1">{c.days_in_stage} d in stage</div></td>
                <td className="text-xs">{c.current_owner_role}<div className="text-light-text-muted">{c.current_owner_role === "JE" ? c.reported_by?.name : c.current_owner_role === "AE" ? c.assigned_ae?.name : c.assigned_jc?.name}</div></td>
                <td className="text-xs">{c.status === "SCN_SERVED" ? <span>Reply by <b>{fmtDate(c.response_due_at)}</b></span> : c.status === "ORDER_SERVED" ? <span>Comply by <b className="text-danger-600">{fmtDate(c.compliance_due_at)}</b></span> : c.stage_due_at ? <span className={new Date(c.stage_due_at) < new Date() ? "text-danger-600" : ""}>SLA {fmtDate(c.stage_due_at)}</span> : "-"}</td>
                <td className="text-xs text-light-text-muted">{ago(c.updated_at)}</td>
              </tr>))}</tbody>
          </table>
        )}
        {q.data && <div className="px-3 pb-3"><Pager count={q.data.count} page={page} pageSize={25} onPage={(n) => set("page", String(n))} /></div>}
      </div>
    </div>
  );
}
