import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { masters } from "@/api/endpoints";
import type { WorkflowConfig, WorkflowStage } from "@/api/types";

type Slot = "REPORTER" | "REVIEWER" | "AUTHORITY";
const FALLBACK: Record<Slot, string> = { REPORTER: "JE", REVIEWER: "AE", AUTHORITY: "JC" };
/** Statuses whose label names a stage of the chain - these always come from the server configuration. */
const CHAIN_STATUSES = new Set(["DRAFT", "PENDING_AE", "RETURNED_TO_JE", "PENDING_JC", "RESPONSE_PENDING_AE", "RESPONSE_PENDING_JC"]);

/**
 * The review hierarchy as configured in Administration → Hierarchy (roles, stages, and the status / action
 * labels derived from them). Fetched once per session; every helper falls back to the code or the given
 * default until the configuration has arrived, so screens never wait for it.
 */
export function useWorkflowConfig() {
  const { i18n } = useTranslation();
  const q = useQuery({ queryKey: ["workflow-config"], queryFn: masters.workflowConfig, staleTime: 5 * 60_000 });
  const cfg: WorkflowConfig | undefined = q.data;
  const hi = !!i18n.language?.startsWith("hi");
  return useMemo(() => {
    const stage = (slot: Slot, index = 0): WorkflowStage | undefined => (slot === "REVIEWER" ? cfg?.slots.REVIEWER[index] : cfg?.slots[slot]);
    const roleLabel = (code?: string | null, short = false) => {
      if (!code) return "";
      const r = cfg?.roles.find((x) => x.code === code);
      if (!r) return code;
      return short ? r.short_label || code : hi && r.label_hi ? r.label_hi : r.label_en;
    };
    const stageLabel = (slot: Slot, index = 0) => { const s = stage(slot, index); return s ? (hi && s.label_hi ? s.label_hi : s.label_en) : FALLBACK[slot]; };
    const stageShort = (slot: Slot, index = 0) => { const s = stage(slot, index); return s ? roleLabel(s.role, true) : FALLBACK[slot]; };
    const slotRoles = (slot: Slot): string[] => { const s = slot === "REVIEWER" ? cfg?.slots.REVIEWER : cfg?.slots[slot] ? [cfg.slots[slot]] : undefined; return s?.length ? s.map((x) => x.role) : [FALLBACK[slot]]; };
    /** `display` = the server-rendered label of one case (stage-specific, e.g. "Pending with Executive Engineer"); used for chain statuses. */
    const statusLabel = (code: string, fallback?: string, display?: string | null) => { if (display && CHAIN_STATUSES.has(code)) return display; const s = cfg?.statuses[code]; if (s && CHAIN_STATUSES.has(code)) return (hi && s.label_hi) || s.label_en; return fallback ?? s?.label_en ?? code; };
    const actionLabel = (code: string, fallback?: string) => { const a = cfg?.actions[code]; if (!a) return fallback ?? code; return (hi && a.label_hi) || a.label_en; };
    return {
      cfg, hi, ready: !!cfg, roles: cfg?.roles || [], stages: cfg?.stages || [], reviewers: cfg?.slots.REVIEWER || [], reviewEnabled: cfg?.review_enabled ?? true,
      summary: cfg?.summary || "JE → AE → JC", managementRoles: cfg?.management_roles || ["ADMIN", "COMMISSIONER", "ADDL_COMMISSIONER"],
      roleLabel, stageLabel, stageShort, slotRoles, statusLabel, actionLabel,
      slotOf: (role?: string | null) => (cfg?.stages.find((s) => s.role === role)?.slot as Slot | undefined),
    };
  }, [cfg, hi]);
}
