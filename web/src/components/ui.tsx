import * as Dialog from "@radix-ui/react-dialog";
import { clsx } from "clsx";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { LAND_COLORS, SEVERITY_COLORS, STATUS_COLORS } from "@/utils/format";

export function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  return <span className={clsx("badge whitespace-nowrap", STATUS_COLORS[status] || "bg-gray-100 text-gray-700")}>{t(`status.${status}`, status)}</span>;
}
export function LandBadge({ land }: { land: string }) {
  const { t } = useTranslation();
  return <span className={clsx("badge", LAND_COLORS[land] || "bg-gray-100")}>{t(`land.${land}`, land)}</span>;
}
export function SeverityBadge({ s }: { s: string }) {
  return <span className={clsx("badge", SEVERITY_COLORS[s] || "bg-gray-100")}>{s}</span>;
}

export function KPI({ label, value, sub, icon, tone = "primary", onClick }: { label: string; value: ReactNode; sub?: string; icon: ReactNode; tone?: "primary" | "accent" | "success" | "warning" | "danger" | "secondary"; onClick?: () => void }) {
  const tones: Record<string, string> = { primary: "bg-primary-100 text-primary-600", accent: "bg-accent-100 text-accent-600", success: "bg-success-100 text-success-600", warning: "bg-warning-100 text-warning-600", danger: "bg-danger-100 text-danger-600", secondary: "bg-secondary-100 text-secondary-600" };
  return (
    <button type="button" onClick={onClick} className={clsx("kpi text-left w-full", onClick && "hover:shadow-panel transition-shadow")}>
      <div className={clsx("icon", tones[tone])}>{icon}</div>
      <div className="min-w-0">
        <div className="text-2xl font-bold leading-tight text-light-text dark:text-dark-text">{value}</div>
        <div className="text-sm font-medium truncate">{label}</div>
        {sub && <div className="text-xs text-light-text-muted truncate">{sub}</div>}
      </div>
    </button>
  );
}

export function Card({ title, children, className, actions }: { title?: ReactNode; children: ReactNode; className?: string; actions?: ReactNode }) {
  return (
    <div className={clsx("card", className)}>
      {(title || actions) && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-light-border dark:border-dark-border">
          <h3 className="font-semibold text-light-text dark:text-dark-text">{title}</h3>
          {actions}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; wide?: boolean }) {
  // Radix UI Dialog primitive (focus trap, Escape, scroll lock, aria) - same primitives as the MCG platform portal.
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content aria-describedby={undefined} className={clsx("fixed z-50 left-1/2 top-8 -translate-x-1/2 w-[calc(100%-2rem)] card max-h-[calc(100vh-4rem)] overflow-y-auto focus:outline-none", wide ? "max-w-4xl" : "max-w-2xl")}>
          <div className="flex items-center justify-between px-5 py-3 border-b border-light-border dark:border-dark-border">
            <Dialog.Title className="font-semibold">{title}</Dialog.Title>
            <Dialog.Close className="p-1 rounded hover:bg-gray-100" aria-label="Close"><X className="h-5 w-5" /></Dialog.Close>
          </div>
          <div className="p-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function Field({ label, children, hint, required }: { label: string; children: ReactNode; hint?: string; required?: boolean }) {
  return (
    <label className="block">
      <span className="label">{label}{required && <span className="text-danger-500"> *</span>}</span>
      {children}
      {hint && <span className="text-xs text-light-text-muted">{hint}</span>}
    </label>
  );
}

export function Empty({ text }: { text?: string }) {
  const { t } = useTranslation();
  return <div className="py-10 text-center text-sm text-light-text-muted">{text || t("common.none")}</div>;
}

export function Spinner() {
  return <div className="flex justify-center py-8"><div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-200 border-t-primary-600" /></div>;
}

export function Alert({ kind = "info", children }: { kind?: "info" | "error" | "success" | "warning"; children: ReactNode }) {
  const map = { info: "bg-blue-50 text-blue-800 border-blue-200", error: "bg-danger-50 text-danger-700 border-danger-100", success: "bg-success-50 text-success-700 border-success-100", warning: "bg-warning-50 text-warning-600 border-warning-100" };
  return <div className={clsx("rounded-lg border px-3 py-2 text-sm", map[kind])}>{children}</div>;
}

export function Pager({ count, page, pageSize, onPage }: { count: number; page: number; pageSize: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  return (
    <div className="flex items-center justify-between text-sm text-light-text-muted pt-3">
      <span>{count} records</span>
      <div className="flex gap-1">
        <button className="btn-outline px-2 py-1" disabled={page <= 1} onClick={() => onPage(page - 1)}>Prev</button>
        <span className="px-2 py-1">Page {page} / {pages}</span>
        <button className="btn-outline px-2 py-1" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}


/** Anti-spoofing verdict for a geotag (see backend services/location_integrity.py). */
export const INTEGRITY_TEXT: Record<string, string> = {
  MOCK_LOCATION: "mock / fake GPS app", SIMULATED_LOCATION: "software-simulated location", ROOTED_DEVICE: "rooted / jailbroken device", EMULATOR: "emulator",
  DEVELOPER_OPTIONS: "Developer options on", VPN_ACTIVE: "VPN active", PROXY_CONFIGURED: "proxy configured", IP_VPN_OR_PROXY: "VPN / proxy IP", IP_HOSTING: "hosting IP",
  HTTP_PROXY_HEADERS: "HTTP proxy headers", IP_FAR_FROM_GPS: "IP far from GPS", STALE_FIX: "stale GPS fix", FUTURE_TIMESTAMP: "device clock ahead", POOR_ACCURACY: "poor GPS accuracy",
  STATIC_FIX: "identical consecutive fixes", IMPLAUSIBLE_TRAVEL: "impossible travel speed", NO_NATIVE_INTEGRITY: "no native anti-spoofing checks", NATIVE_CHECKS_UNAVAILABLE: "native checks unavailable (Expo Go)",
  WEB_UNVERIFIED: "browser location (unverified)", WEB_GEOTAG: "browser geotag refused", ATTESTATION_MISSING: "no device attestation", ATTESTATION_FAILED: "device attestation failed", NO_SIGNALS: "no device signals",
};
export function IntegrityBadge({ status, reasons = [], compact }: { status?: string | null; reasons?: string[]; compact?: boolean }) {
  if (!status || status === "UNVERIFIED") return null;
  const tone = status === "PASS" ? "bg-success-50 text-success-600" : status === "FLAGGED" ? "bg-warning-50 text-warning-600" : "bg-danger-50 text-danger-600";
  const label = status === "PASS" ? "Location trusted" : status === "FLAGGED" ? "Location flagged" : "Location rejected";
  const why = reasons.map((r) => INTEGRITY_TEXT[r] || r).join(", ");
  return <span className={`badge ${tone}`} title={why || label}>{compact ? label : `${label}${why ? ` · ${why}` : ""}`}</span>;
}
