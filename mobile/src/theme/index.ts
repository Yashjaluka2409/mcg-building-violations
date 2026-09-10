/** Design tokens copied from the MCG HARYANA app / MCG platform (purple header, off-white ground,
 *  rounded white cards, green status pills, teal/amber accents). Single source for the whole app. */
export const colors = {
  primary: "#782669", primaryDark: "#5a1a4d", primaryDarker: "#4a153f", primaryLight: "#a55cb4", primary50: "#f9f5f7", primary100: "#f2e7ed",
  accent: "#0d9488", accent100: "#d1faf8",
  secondary: "#f59e0b", secondary100: "#fef3c7",
  success: "#2e7d32", success100: "#dcfce7",
  danger: "#d32f2f", danger100: "#fee2e2",
  bg: "#f7f7fb", surface: "#ffffff", border: "#e5e7eb",
  text: "#1f2937", muted: "#6b7280", white: "#ffffff",
};
export const radius = { sm: 8, md: 12, lg: 16, xl: 22, pill: 999 };
export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 };
export const shadow = { shadowColor: "#000", shadowOpacity: 0.06, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 2 };
export const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
  DRAFT: { bg: "#f3f4f6", fg: "#374151" }, PENDING_AE: { bg: "#dbeafe", fg: "#1d4ed8" }, RETURNED_TO_JE: { bg: "#fef3c7", fg: "#b45309" }, PENDING_JC: { bg: "#e0e7ff", fg: "#4338ca" },
  SCN_ISSUED: { bg: "#f2e7ed", fg: "#782669" }, SCN_SERVED: { bg: "#ddbee2", fg: "#4a153f" }, RESPONSE_PENDING_AE: { bg: "#cffafe", fg: "#0e7490" }, RESPONSE_PENDING_JC: { bg: "#cffafe", fg: "#0e7490" },
  RESPONSE_RECEIVED: { bg: "#cffafe", fg: "#0e7490" }, NO_RESPONSE: { bg: "#ffedd5", fg: "#c2410c" }, HEARING_SCHEDULED: { bg: "#ede9fe", fg: "#6d28d9" }, ORDER_ISSUED: { bg: "#fee2e2", fg: "#b91c1c" },
  ORDER_SERVED: { bg: "#fecaca", fg: "#991b1b" }, APPEAL_STAY: { bg: "#e2e8f0", fg: "#334155" }, EXECUTION_DUE: { bg: "#dc2626", fg: "#ffffff" }, COMPLIED: { bg: "#dcfce7", fg: "#166534" },
  EXECUTED: { bg: "#bbf7d0", fg: "#166534" }, CLOSED: { bg: "#e5e7eb", fg: "#374151" }, DROPPED: { bg: "#f3f4f6", fg: "#6b7280" }, REGULARISED: { bg: "#d1fae5", fg: "#065f46" },
};
