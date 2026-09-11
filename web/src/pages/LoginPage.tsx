import { Building2, FileSignature, Gavel, Phone, ShieldCheck, Smartphone } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import { auth } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { useAuth } from "@/store/auth";

/** Login page laid out exactly like the MCG platform's landing (hero + stat tiles left, OTP card right). */
export default function LoginPage() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const loc = useLocation() as any;
  const setTokens = useAuth((s) => s.setTokens);
  const [mobile, setMobile] = useState("");
  const [otp, setOtp] = useState("");
  const [stage, setStage] = useState<"mobile" | "otp">("mobile");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const send = async () => { setBusy(true); setErr(""); try { await auth.requestOtp(mobile); setStage("otp"); } catch (e) { setErr(errorMessage(e)); } setBusy(false); };
  const verify = async () => { setBusy(true); setErr(""); try { const r = await auth.verifyOtp(mobile, otp); setTokens(r.access_token, r.refresh_token, r.user); nav(loc.state?.from?.pathname || "/dashboard", { replace: true }); } catch (e) { setErr(errorMessage(e)); } setBusy(false); };
  const tiles = [
    { icon: Building2, v: "36", l: "Wards", s: "Across 4 Zones", c: "bg-primary-100 text-primary-600" },
    { icon: FileSignature, v: "QR", l: "Signed notices", s: "Digitally signed & verifiable", c: "bg-accent-100 text-accent-600" },
    { icon: Gavel, v: "s.261", l: "HMC Act 1994", s: "Show cause → order → execution", c: "bg-success-100 text-success-600" },
    { icon: Smartphone, v: "GPS", l: "Geotagged evidence", s: "Photos, videos, delivery proof", c: "bg-secondary-100 text-secondary-600" },
  ];
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#eff6ff] via-white to-[#f0fdf4] flex items-center">
      <div className="max-w-6xl w-full mx-auto grid lg:grid-cols-2 gap-10 p-8">
        <div className="space-y-6">
          <img src="/brand/mcg-logo.png" alt="MCG" className="h-16 object-contain" />
          <div>
            <h1 className="text-5xl lg:text-6xl font-bold text-light-text leading-tight">{t("login.hero1")}</h1>
            <h2 className="text-4xl lg:text-5xl font-bold hero-gradient">{t("login.hero2")}</h2>
          </div>
          <p className="text-lg text-light-text-muted max-w-lg leading-relaxed">{t("login.blurb")}</p>
          <div className="grid grid-cols-2 gap-4 max-w-lg">
            {tiles.map((x) => (
              <div key={x.l} className="card p-4 flex items-start gap-3">
                <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${x.c}`}><x.icon className="h-5 w-5" /></div>
                <div><div className="text-2xl font-bold text-light-text">{x.v}</div><div className="text-sm font-medium">{x.l}</div><div className="text-xs text-light-text-muted">{x.s}</div></div>
              </div>
            ))}
          </div>
          <ul className="text-sm text-light-text-muted space-y-1">
            <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-primary-500" />Configurable review chain (default JE → AE → Joint Commissioner) with SLA escalation</li>
            <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-accent-500" />PID-linked SMS delivery and affixation proof</li>
            <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-secondary-500" />Tamper-evident audit trail (s.403, HMC Act)</li>
          </ul>
        </div>
        <div className="flex items-center justify-center">
          <div className="card w-full max-w-md p-8 space-y-5">
            <div className="text-center"><img src="/brand/mcg-login-logo.svg" alt="" className="h-14 mx-auto mb-2" /><div className="font-semibold text-lg">{t("login.welcome")}</div><div className="text-sm text-light-text-muted">{t("login.sign_in")}</div></div>
            {stage === "mobile" ? (
              <>
                <label className="block"><span className="label flex items-center gap-1"><Phone className="h-3 w-3" />{t("login.mobile")}</span>
                  <div className="flex"><span className="inline-flex items-center px-3 rounded-l-lg border border-r-0 border-light-border bg-gray-50 text-sm">+91</span><input className="input rounded-l-none" placeholder="Enter your 10-digit mobile number" value={mobile} onChange={(e) => setMobile(e.target.value.replace(/\D/g, "").slice(0, 10))} onKeyDown={(e) => e.key === "Enter" && send()} /></div></label>
                <button className="btn-primary w-full py-3" disabled={mobile.length !== 10 || busy} onClick={send}><ShieldCheck className="h-4 w-4" />{t("login.send_otp")}</button>
              </>
            ) : (
              <>
                <label className="block"><span className="label">{t("login.otp")} · +91 {mobile}</span><input className="input text-center tracking-[0.5em] text-lg" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))} onKeyDown={(e) => e.key === "Enter" && verify()} autoFocus /></label>
                <button className="btn-primary w-full py-3" disabled={otp.length < 4 || busy} onClick={verify}>{t("login.verify")}</button>
                <button className="btn-ghost w-full" onClick={() => setStage("mobile")}>{t("login.change")}</button>
              </>
            )}
            {err && <div className="text-sm text-danger-600 text-center">{err}</div>}
            <div className="text-[11px] text-center text-light-text-muted pt-2 border-t border-light-border">● System Online &nbsp; ⇄ Building Violation Module</div>
          </div>
        </div>
      </div>
    </div>
  );
}
