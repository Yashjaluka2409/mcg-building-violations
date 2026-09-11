import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Bell, Building, CalendarClock, FileSignature, Gavel, Hammer, Landmark, Lock, MailWarning, Scale, ShieldAlert, Timer, TrendingUp } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useWorkflowConfig } from "@/hooks/useWorkflowConfig";
import { useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dashboards, masters } from "@/api/endpoints";
import { Card, KPI, Spinner } from "@/components/ui";
import { fmtDate, inr, num } from "@/utils/format";
import MapView from "@/components/MapView";

const PALETTE = ["#782669", "#0d9488", "#f59e0b", "#2563eb", "#dc2626", "#16a34a", "#7c3aed", "#0891b2", "#a55cb4", "#b45309"];

export default function DashboardPage() {
  const { t } = useTranslation();
  const wf = useWorkflowConfig();
  const nav = useNavigate();
  const [f, setF] = useState<Record<string, string>>({});
  const zones = useQuery({ queryKey: ["zones"], queryFn: masters.zones });
  const wards = useQuery({ queryKey: ["wards", f.zone], queryFn: () => masters.wards(f.zone ? Number(f.zone) : undefined) });
  const summary = useQuery({ queryKey: ["dash-summary", f], queryFn: () => dashboards.summary(f) });
  const funnel = useQuery({ queryKey: ["dash-funnel", f], queryFn: () => dashboards.funnel(f) });
  const area = useQuery({ queryKey: ["dash-area", f], queryFn: () => dashboards.byArea({ ...f, by: f.zone ? "ward" : "zone" }) });
  const mix = useQuery({ queryKey: ["dash-mix", f], queryFn: () => dashboards.mix(f) });
  const trends = useQuery({ queryKey: ["dash-trends", f], queryFn: () => dashboards.trends(f) });
  const sla = useQuery({ queryKey: ["dash-sla", f], queryFn: () => dashboards.sla(f) });
  const ageing = useQuery({ queryKey: ["dash-ageing", f], queryFn: () => dashboards.ageing(f) });
  const deadlines = useQuery({ queryKey: ["dash-deadlines", f], queryFn: () => dashboards.deadlines({ ...f, days: 7 }) });
  const officers = useQuery({ queryKey: ["dash-officers", f], queryFn: () => dashboards.officers(f) });
  const points = useQuery({ queryKey: ["dash-map", f], queryFn: () => dashboards.map({ ...f, open: 1 }) });
  const s = summary.data;
  const go = (params: Record<string, string>) => nav(`/cases?${new URLSearchParams({ ...f, ...params }).toString()}`);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <div><h1 className="page-title">{t("nav.dashboard")}</h1><p className="page-sub">Building violations, notices, orders and enforcement - live MIS</p></div>
        <div className="flex-1" />
        <select className="input w-40" value={f.zone || ""} onChange={(e) => setF({ ...f, zone: e.target.value, ward: "" })}><option value="">{t("common.all")} {t("common.zone")}s</option>{zones.data?.map((z) => <option key={z.id} value={z.id}>Zone {z.code}</option>)}</select>
        <select className="input w-40" value={f.ward || ""} onChange={(e) => setF({ ...f, ward: e.target.value })}><option value="">{t("common.all")} {t("common.ward")}s</option>{wards.data?.map((w) => <option key={w.id} value={w.id}>Ward {w.number}</option>)}</select>
        <input type="date" className="input w-40" value={f.from || ""} onChange={(e) => setF({ ...f, from: e.target.value })} />
        <input type="date" className="input w-40" value={f.to || ""} onChange={(e) => setF({ ...f, to: e.target.value })} />
        <button className="btn-outline" onClick={() => setF({})}>{t("common.reset")}</button>
      </div>
      {!s ? <Spinner /> : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
            <KPI label="Open cases" value={num(s.cases_open)} sub={`${num(s.cases_total)} total · ${num(s.cases_new_30d)} new in 30 days`} icon={<Building className="h-5 w-5" />} onClick={() => go({})} />
            <KPI label="On government land" value={num(s.govt_land_cases)} sub="MCG + State land" icon={<Landmark className="h-5 w-5" />} tone="danger" onClick={() => go({ land_type: "GOVT_MCG" })} />
            <KPI label={`Pending with ${wf.stageShort("REVIEWER")} / ${wf.stageShort("AUTHORITY")}`} value={`${num(s.pending_ae)} / ${num(s.pending_jc)}`} sub="awaiting review / orders" icon={<Scale className="h-5 w-5" />} tone="accent" onClick={() => go({ status: "PENDING_JC" })} />
            <KPI label="SCN issued" value={num(s.scn_issued)} sub={`${num(s.scn_pending_service)} to be served · ${num(s.responses_awaited)} replies awaited`} icon={<FileSignature className="h-5 w-5" />} onClick={() => go({ status: "SCN_ISSUED" })} />
            <KPI label="Demolition / sealing orders" value={`${num(s.demolition_orders)} / ${num(s.sealing_orders)}`} sub={`${num(s.stop_work_orders)} stop-work orders`} icon={<Gavel className="h-5 w-5" />} tone="secondary" onClick={() => go({ status: "ORDER_SERVED" })} />
            <KPI label="Execution due" value={num(s.execution_due)} sub={`${num(s.compliance_running)} in compliance period · ${num(s.stayed)} stayed`} icon={<Hammer className="h-5 w-5" />} tone="danger" onClick={() => go({ status: "EXECUTION_DUE" })} />
            <KPI label="Demolished by MCG" value={num(s.demolished)} sub={`${num(s.self_complied)} complied by owners`} icon={<Hammer className="h-5 w-5" />} tone="success" />
            <KPI label="Sealed premises" value={num(s.sealed)} icon={<Lock className="h-5 w-5" />} tone="warning" onClick={() => go({ sealed: "true" })} />
            <KPI label="No reply in time" value={num(s.no_response)} sub="ex parte decision pending" icon={<MailWarning className="h-5 w-5" />} tone="warning" onClick={() => go({ status: "NO_RESPONSE" })} />
            <KPI label="SLA breached (open)" value={num(s.sla_breached_open)} icon={<AlertTriangle className="h-5 w-5" />} tone="danger" onClick={() => go({ sla_breached: "true" })} />
            <KPI label="Closed / dropped / regularised" value={`${num(s.closed)} / ${num(s.dropped)} / ${num(s.regularised)}`} icon={<ShieldAlert className="h-5 w-5" />} tone="success" />
            <KPI label="Demolition cost booked" value={inr(s.demolition_cost_inr)} sub={`${num(s.cost_recovery_pending)} recoveries pending`} icon={<TrendingUp className="h-5 w-5" />} tone="accent" />
            <KPI label="Planned inspections open" value={num(s.tasks_open)} sub={`${num(s.tasks_overdue)} overdue · ${num(s.tasks_violation_found)} violations found · ${num(s.tasks_no_violation)} clear`} icon={<CalendarClock className="h-5 w-5" />} tone="secondary" onClick={() => nav("/tasks")} />
            <KPI label="Stayed by courts" value={`${num(s.stayed_high_court)} HC / ${num(s.stayed_supreme_court)} SC / ${num(s.stayed_divisional_commissioner)} DC`} sub={`${num(s.litigation_pending)} appeals pending · ${num(s.stays_expiring_7d)} stays expiring in 7 d`} icon={<Scale className="h-5 w-5" />} tone="primary" onClick={() => go({ litigation_status: "STAYED" })} />
            <KPI label="Branch referrals pending" value={num(s.referrals_pending)} sub={`${num(s.referrals_overdue)} overdue`} icon={<Bell className="h-5 w-5" />} tone="accent" onClick={() => nav("/referrals")} />
            <KPI label="GPS spoofing blocked (30 d)" value={num(s.integrity_rejected_30d)} sub={`${num(s.integrity_flagged_30d)} flagged of ${num(s.integrity_checked_30d)} location checks`} icon={<ShieldAlert className="h-5 w-5" />} tone={s.integrity_rejected_30d > 0 ? "danger" : "success"} onClick={() => nav("/reports?name=location-integrity")} />
          </div>
          {(s.signature_failed > 0 || s.sms_failed > 0) && <div className="rounded-lg border border-warning-100 bg-warning-50 text-warning-600 px-3 py-2 text-sm flex items-center gap-2"><Bell className="h-4 w-4" />{s.signature_failed} notice(s) could not be digitally signed and {s.sms_failed} SMS dispatch(es) failed - check the signer / SMS gateway configuration.</div>}
          <div className="grid lg:grid-cols-3 gap-4">
            <Card title="Workflow funnel" className="lg:col-span-2">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={(funnel.data || []).filter((x) => x.count > 0)} margin={{ left: 0, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={70} /><YAxis allowDecimals={false} /><Tooltip />
                  <Bar dataKey="count" name="Cases" fill="#782669" radius={[4, 4, 0, 0]} onClick={(d: any) => go({ status: d.status })} cursor="pointer" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Violations by category">
              <ResponsiveContainer width="100%" height={280}>
                <PieChart><Pie data={mix.data?.by_category || []} dataKey="count" nameKey="category" innerRadius={55} outerRadius={95} paddingAngle={2}>{(mix.data?.by_category || []).map((_: any, i: number) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}</Pie><Tooltip /><Legend wrapperStyle={{ fontSize: 10 }} /></PieChart>
              </ResponsiveContainer>
            </Card>
          </div>
          <div className="grid lg:grid-cols-3 gap-4">
            <Card title={f.zone ? "Ward-wise" : "Zone-wise"} className="lg:col-span-2">
              <div className="overflow-x-auto"><table className="table">
                <thead><tr><th>{f.zone ? "Ward" : "Zone"}</th><th>Total</th><th>Open</th><th>Govt land</th><th>SCN</th><th>Orders</th><th>Executed/closed</th><th>SLA breached</th></tr></thead>
                <tbody>{(area.data || []).map((r: any) => <tr key={r.key} className="hover:bg-gray-50 cursor-pointer" onClick={() => setF({ ...f, [f.zone ? "ward" : "zone"]: String(zones.data?.find((z) => z.code === String(r.key))?.id ?? wards.data?.find((w) => String(w.number) === String(r.key))?.id ?? "") })}><td className="font-medium">{f.zone ? "Ward" : "Zone"} {r.key ?? "-"}</td><td>{r.total}</td><td>{r.open}</td><td>{r.govt}</td><td>{r.scn}</td><td>{r.orders}</td><td>{r.executed}</td><td className={r.breached ? "text-danger-600 font-semibold" : ""}>{r.breached}</td></tr>)}</tbody>
              </table></div>
            </Card>
            <Card title="Top violation types">
              <div className="space-y-2">{(mix.data?.by_type || []).slice(0, 8).map((r: any, i: number) => (
                <div key={r.code} className="text-sm"><div className="flex justify-between"><span className="truncate pr-2"><span className="font-mono text-xs text-primary-600">{r.code}</span> {r.title}</span><span className="font-semibold">{r.count}</span></div><div className="h-1.5 bg-gray-100 rounded"><div className="h-1.5 rounded" style={{ width: `${Math.min(100, (r.count / (mix.data.by_type[0]?.count || 1)) * 100)}%`, background: PALETTE[i % PALETTE.length] }} /></div></div>))}</div>
            </Card>
          </div>
          <div className="grid lg:grid-cols-3 gap-4">
            <Card title="Monthly trend" className="lg:col-span-2">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={trends.data || []}><CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="period" tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} /><Tooltip /><Legend />
                  <Line type="monotone" dataKey="new_cases" name="New cases" stroke="#782669" strokeWidth={2} /><Line type="monotone" dataKey="notices" name="Notices" stroke="#0d9488" strokeWidth={2} /><Line type="monotone" dataKey="orders" name="Final orders" stroke="#f59e0b" strokeWidth={2} /><Line type="monotone" dataKey="demolitions" name="Demolitions" stroke="#dc2626" strokeWidth={2} /><Line type="monotone" dataKey="closed" name="Closed" stroke="#16a34a" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Ageing of open cases">
              <ResponsiveContainer width="100%" height={180}><BarChart data={ageing.data?.buckets || []}><XAxis dataKey="bucket" tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="count" name="Cases" fill="#0d9488" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer>
              <div className="text-xs text-light-text-muted mt-2 space-y-1">{(ageing.data?.avg_days_in_stage || []).slice(0, 6).map((r: any) => <div key={r.status} className="flex justify-between"><span>{t(`status.${r.status}`)}</span><span>{r.avg_days} d avg · {r.count}</span></div>)}</div>
            </Card>
          </div>
          <div className="grid lg:grid-cols-3 gap-4">
            <Card title={<span className="flex items-center gap-2"><CalendarClock className="h-4 w-4" />Deadlines in next 7 days</span>}>
              <div className="space-y-3 text-sm max-h-80 overflow-y-auto">
                {["responses_due", "compliance_due", "hearings", "stays_expiring"].map((k) => (
                  <div key={k}><div className="label">{k.replace(/_/g, " ")}</div>{(deadlines.data?.[k] || []).length ? (deadlines.data[k] as any[]).map((r) => <button key={r.id} className="block w-full text-left py-1 border-b border-light-border hover:text-primary-600" onClick={() => nav(`/cases/${r.id}`)}><span className="font-mono text-xs">{r.case_no}</span> · Ward {r.ward ?? "-"} · <span className="text-danger-600">{fmtDate(r.due)}</span><div className="text-xs text-light-text-muted truncate">{r.address}</div></button>) : <div className="text-xs text-light-text-muted">None</div>}</div>))}
              </div>
            </Card>
            <Card title={<span className="flex items-center gap-2"><Timer className="h-4 w-4" />Turnaround (average hours)</span>}>
              <table className="table text-xs"><tbody>{Object.entries(sla.data?.avg_hours || {}).map(([k, v]) => <tr key={k}><td>{k.replace(/_/g, " ")}</td><td className="text-right font-semibold">{v == null ? "-" : `${v} h`}</td></tr>)}</tbody></table>
              <div className="label mt-3">Open by owner role</div>
              <table className="table text-xs"><thead><tr><th>Role</th><th>Open</th><th>Overdue</th><th>Breached</th></tr></thead><tbody>{(sla.data?.by_owner_role || []).map((r: any) => <tr key={r.current_owner_role}><td>{r.current_owner_role}</td><td>{r.total}</td><td>{r.overdue}</td><td className="text-danger-600">{r.breached}</td></tr>)}</tbody></table>
            </Card>
            <Card title="Officer performance">
              <div className="text-xs space-y-3 max-h-80 overflow-y-auto">
                {(["je", "ae", "jc"] as const).map((k) => <div key={k}><div className="label">{k.toUpperCase()}</div><table className="table text-xs"><tbody>{(officers.data?.[k] || []).map((r: any) => <tr key={r.user_id}><td>{r.name}</td><td>{r.cases} cases</td><td>{r.pending != null ? `${r.pending} pending` : `${r.submitted} submitted`}</td><td className={r.overdue ? "text-danger-600" : ""}>{r.overdue} overdue</td></tr>)}</tbody></table></div>)}
              </div>
            </Card>
          </div>
          <Card title="Open cases map" actions={<button className="btn-ghost text-xs" onClick={() => nav("/map")}>Open full map</button>}><MapView points={points.data} fit legend height="380px" onOpenCase={(id) => nav(`/cases/${id}`)} /></Card>
        </>
      )}
    </div>
  );
}
