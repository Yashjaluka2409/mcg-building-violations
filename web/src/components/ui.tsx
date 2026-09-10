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
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 overflow-y-auto" onClick={onClose}>
      <div className={clsx("card w-full mt-8 mb-8", wide ? "max-w-4xl" : "max-w-2xl")} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-light-border dark:border-dark-border">
          <h3 className="font-semibold">{title}</h3>
          <button className="p-1 rounded hover:bg-gray-100" onClick={onClose}><X className="h-5 w-5" /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
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
