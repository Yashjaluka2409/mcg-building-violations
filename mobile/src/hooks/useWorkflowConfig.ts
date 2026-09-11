import AsyncStorage from "@react-native-async-storage/async-storage";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { masters } from "@/api/endpoints";

type Slot = "REPORTER" | "REVIEWER" | "AUTHORITY";
const FALLBACK: Record<Slot, string> = { REPORTER: "JE", REVIEWER: "AE", AUTHORITY: "JC" };
const CHAIN_STATUSES = new Set(["DRAFT", "PENDING_AE", "RETURNED_TO_JE", "PENDING_JC", "RESPONSE_PENDING_AE", "RESPONSE_PENDING_JC"]);
const KEY = "workflowConfig";
let cached: any = null;
AsyncStorage.getItem(KEY).then((v) => { if (v && !cached) { try { cached = JSON.parse(v); } catch { /* ignore */ } } }).catch(() => undefined);

/** The review hierarchy configured by the admin (Administration → Hierarchy on the portal): role / stage /
 *  status / action labels. Cached on the device so the field app shows the right names even offline. */
export function useWorkflowConfig() {
  const { i18n } = useTranslation();
  const q = useQuery({
    queryKey: ["workflow-config"], staleTime: 10 * 60_000, placeholderData: () => cached,
    queryFn: async () => { const d = await masters.workflowConfig(); cached = d; AsyncStorage.setItem(KEY, JSON.stringify(d)).catch(() => undefined); return d; },
  });
  const cfg: any = q.data || cached;
  const hi = !!i18n.language?.startsWith("hi");
  return useMemo(() => {
    const stage = (slot: Slot, index = 0) => (slot === "REVIEWER" ? cfg?.slots?.REVIEWER?.[index] : cfg?.slots?.[slot]);
    const roleLabel = (code?: string | null, short = false) => { if (!code) return ""; const r = cfg?.roles?.find((x: any) => x.code === code); if (!r) return code; return short ? r.short_label || code : hi && r.label_hi ? r.label_hi : r.label_en; };
    const stageLabel = (slot: Slot, index = 0) => { const s = stage(slot, index); return s ? (hi && s.label_hi ? s.label_hi : s.label_en) : FALLBACK[slot]; };
    /** `display` = the server-rendered label of a particular case (stage-specific, e.g. "Pending with Executive Engineer"). */
    const statusLabel = (code: string, fallback?: string, display?: string | null) => { if (display && CHAIN_STATUSES.has(code)) return display; const s = cfg?.statuses?.[code]; if (s && CHAIN_STATUSES.has(code)) return (hi && s.label_hi) || s.label_en; return fallback ?? s?.label_en ?? code.replace(/_/g, " "); };
    const actionLabel = (code: string, fallback?: string) => { const a = cfg?.actions?.[code]; if (!a) return fallback ?? code; return (hi && a.label_hi) || a.label_en; };
    return { cfg, hi, ready: !!cfg, roleLabel, stageLabel, statusLabel, actionLabel, reviewEnabled: cfg?.review_enabled ?? true, summary: cfg?.summary || "JE → AE → JC" };
  }, [cfg, hi]);
}
