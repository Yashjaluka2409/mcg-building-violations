import { format, formatDistanceToNowStrict, parseISO } from "date-fns";

export const fmtDate = (v?: string | null) => (v ? format(parseISO(v), "dd-MM-yyyy") : "-");
export const fmtDateTime = (v?: string | null) => (v ? format(parseISO(v), "dd-MM-yyyy HH:mm") : "-");
export const ago = (v?: string | null) => (v ? formatDistanceToNowStrict(parseISO(v), { addSuffix: true }) : "-");
export const daysLeft = (v?: string | null) => (v ? Math.ceil((parseISO(v).getTime() - Date.now()) / 86_400_000) : null);
export const inr = (v?: string | number | null) => (v == null || v === "" ? "-" : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Number(v)));
export const num = (v?: number | null) => new Intl.NumberFormat("en-IN").format(v ?? 0);

export const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700", PENDING_AE: "bg-blue-50 text-blue-700", RETURNED_TO_JE: "bg-amber-50 text-amber-700", PENDING_JC: "bg-indigo-50 text-indigo-700",
  SCN_ISSUED: "bg-primary-50 text-primary-700", SCN_SERVED: "bg-primary-100 text-primary-800", RESPONSE_RECEIVED: "bg-cyan-50 text-cyan-700", RESPONSE_PENDING_AE: "bg-cyan-50 text-cyan-700",
  RESPONSE_PENDING_JC: "bg-cyan-100 text-cyan-800", NO_RESPONSE: "bg-orange-50 text-orange-700", HEARING_SCHEDULED: "bg-violet-50 text-violet-700", ORDER_ISSUED: "bg-danger-50 text-danger-600",
  ORDER_SERVED: "bg-danger-100 text-danger-700", APPEAL_STAY: "bg-slate-100 text-slate-700", EXECUTION_DUE: "bg-red-600 text-white", COMPLIED: "bg-success-50 text-success-700",
  EXECUTED: "bg-success-100 text-success-700", CLOSED: "bg-gray-200 text-gray-700", DROPPED: "bg-gray-100 text-gray-500", REGULARISED: "bg-emerald-50 text-emerald-700",
};
export const LAND_COLORS: Record<string, string> = { GOVT_MCG: "bg-danger-50 text-danger-600", GOVT_STATE: "bg-orange-50 text-orange-700", PRIVATE: "bg-gray-100 text-gray-700", UNKNOWN: "bg-gray-50 text-gray-500" };
export const SEVERITY_COLORS: Record<string, string> = { CRITICAL: "bg-danger-500 text-white", HIGH: "bg-orange-500 text-white", MEDIUM: "bg-secondary-400 text-white", LOW: "bg-gray-300 text-gray-800" };
