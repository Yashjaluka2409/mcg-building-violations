import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import { useParams, useSearchParams } from "react-router-dom";
import { notices } from "@/api/endpoints";
import { fmtDate, fmtDateTime } from "@/utils/format";

/** Public page opened from the QR code printed on every notice - no login. */
export default function VerifyPage() {
  const { code } = useParams();
  const [sp] = useSearchParams();
  const q = useQuery({ queryKey: ["verify", code], queryFn: () => notices.verifyPublic(code!, sp.get("h") || undefined), retry: false });
  const d = q.data;
  return (
    <div className="min-h-screen bg-light-background flex items-start justify-center p-6">
      <div className="card w-full max-w-lg p-6 space-y-4">
        <div className="text-center"><img src="/brand/mcg-logo.png" alt="MCG" className="h-14 mx-auto" /><div className="font-bold text-primary-700 mt-2">Municipal Corporation Gurugram</div><div className="text-sm text-light-text-muted">Notice / order verification</div></div>
        {q.isLoading ? <div className="text-center text-sm">Checking…</div> : q.isError || !d?.valid ? <div className="rounded-lg bg-danger-50 border border-danger-100 p-4 text-danger-700 flex items-center gap-2"><XCircle className="h-6 w-6" />No notice exists with verification code <b className="font-mono ml-1">{code}</b>. Treat the document as not genuine and report to the helpline.</div> : (
          <>
            <div className={`rounded-lg p-4 flex items-center gap-2 border ${d.hash_match === false ? "bg-warning-50 border-warning-100 text-warning-600" : "bg-success-50 border-success-100 text-success-700"}`}>{d.hash_match === false ? <ShieldAlert className="h-6 w-6" /> : <CheckCircle2 className="h-6 w-6" />}<div><div className="font-semibold">{d.hash_match === false ? "Notice number is genuine, but the document hash does not match" : "Genuine document issued by MCG"}</div><div className="text-xs">{d.signature_status === "SIGNED" ? `Digitally signed by ${d.signer}` : "Signature pending"}{d.superseded && " · superseded by a later order"}</div></div></div>
            <table className="table text-sm"><tbody>{[["Notice no.", d.notice_no], ["Type", d.order_type], ["Provision", `${d.statute} s.${d.section}`], ["Case no.", d.case_no], ["Property", `${d.property.pid ? "PID " + d.property.pid + ", " : ""}${d.property.address}${d.property.ward ? ", Ward " + d.property.ward : ""}`], ["Addressee", d.addressee], ["Issued on", fmtDateTime(d.issued_at)], ["Issued by", `${d.issued_by}, ${d.designation}`], ["Reply due", fmtDate(d.response_due_at)], ["Comply by", fmtDate(d.compliance_due_at)], ["Served on", fmtDate(d.served_at)], ["Case status", d.case_status]].map(([k, v]) => <tr key={k as string}><td className="font-medium w-36">{k}</td><td>{v || "-"}</td></tr>)}</tbody></table>
            <div className="text-[11px] text-light-text-muted break-all">SHA-256 {d.document_hash}</div>
          </>)}
      </div>
    </div>
  );
}
