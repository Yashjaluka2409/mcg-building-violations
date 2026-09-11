import { API_BASE, api } from "./client";
import type { AdminLog, Appeal, Branch, CaseDetail, CaseListItem, GovtParcel, InspectionBatch, InspectionTask, LandLayer, LegalSection, Me, Media, Notice, Notification, OrderType, Paginated, PermMatrix, Referral, RulesMatrix, SanctionedPlan, ViolationType, Ward, WorkflowSetting, Zone } from "./types";

export const auth = {
  requestOtp: (mobile: string) => api.post("/auth/otp/request/", { mobile }).then((r) => r.data),
  verifyOtp: (mobile: string, otp: string) => api.post("/auth/otp/verify/", { mobile, otp }).then((r) => r.data as { access_token: string; refresh_token: string; user: Me }),
  me: () => api.get<Me>("/users/me/").then((r) => r.data),
};
export const masters = {
  zones: () => api.get<Zone[]>("/masters/zones/").then((r) => r.data),
  wards: (zone?: number) => api.get<Ward[]>("/masters/wards/", { params: zone ? { zone } : {} }).then((r) => r.data),
  violationTypes: () => api.get<ViolationType[]>("/masters/violation-types/").then((r) => r.data),
  orderTypes: () => api.get<OrderType[]>("/masters/order-types/").then((r) => r.data),
  legalSections: (params?: Record<string, string>) => api.get<LegalSection[]>("/masters/legal-sections/", { params }).then((r) => r.data),
  statutes: () => api.get("/masters/legal-sections/statutes/").then((r) => r.data as { code: string; title: string; citation: string; jurisdiction: string; primary: boolean; sections: number }[]),
  sla: () => api.get("/masters/sla/").then((r) => r.data),
  officers: (params?: Record<string, string | number>) => api.get("/officers/dropdown/", { params }).then((r) => r.data as { user_id: string; name: string; role: string; designation: string }[]),
};
export const property = {
  lookupPid: (pid: string) => api.get(`/property/pid/${encodeURIComponent(pid)}/`).then((r) => r.data),
  checkPoint: (lat: number, lng: number) => api.get("/gis/check-point/", { params: { lat, lng } }).then((r) => r.data as { land_type: string; parcels: GovtParcel[]; ward: Ward | null }),
  govtLandGeoJson: (bbox?: string) => api.get("/gis/govt-land/geojson/", { params: bbox ? { bbox } : {} }).then((r) => r.data),
  uploadLandLayer: (fd: FormData) => api.post<LandLayer>("/gis/land-layers/", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data),
  landLayers: () => api.get<Paginated<LandLayer>>("/gis/land-layers/", { params: { page_size: 200 } }).then((r) => r.data),
  retireLayer: (id: number) => api.delete(`/gis/land-layers/${id}/`).then((r) => r.data),
  reactivateLayer: (id: number) => api.post<LandLayer>(`/gis/land-layers/${id}/reactivate/`).then((r) => r.data),
};
export const tasks = {
  list: (params: Record<string, unknown>) => api.get<Paginated<InspectionTask>>("/inspections/tasks/", { params }).then((r) => r.data),
  get: (id: number) => api.get<InspectionTask>(`/inspections/tasks/${id}/`).then((r) => r.data),
  counts: () => api.get("/inspections/tasks/counts/").then((r) => r.data as Record<string, number>),
  create: (d: Record<string, unknown>) => api.post<InspectionTask>("/inspections/tasks/", d).then((r) => r.data),
  assign: (id: number, assigned_to: string, remarks = "") => api.post<InspectionTask>(`/inspections/tasks/${id}/assign/`, { assigned_to, remarks }).then((r) => r.data),
  start: (id: number, latitude: number, longitude: number, accuracy_m?: number) => api.post<InspectionTask>(`/inspections/tasks/${id}/start/`, { latitude, longitude, accuracy_m, location_integrity: { source: "web", platform: "web", native_module: false, user_agent: navigator.userAgent } }).then((r) => r.data),
  distance: (id: number, lat: number, lng: number) => api.get(`/inspections/tasks/${id}/distance/`, { params: { lat, lng } }).then((r) => r.data as { distance_m: number | null; geofence_m: number; within: boolean }),
  close: (id: number, d: Record<string, unknown>) => api.post<InspectionTask>(`/inspections/tasks/${id}/close/`, d).then((r) => r.data),
  cancel: (id: number, remarks = "") => api.post<InspectionTask>(`/inspections/tasks/${id}/cancel/`, { remarks }).then((r) => r.data),
  geojson: (params?: Record<string, unknown>) => api.get("/inspections/tasks/geojson/", { params }).then((r) => r.data),
  bulkUpload: (fd: FormData) => api.post<InspectionBatch>("/inspections/tasks/bulk_upload/", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data),
  batches: () => api.get<Paginated<InspectionBatch>>("/inspections/batches/", { params: { page_size: 50 } }).then((r) => r.data),
};
export const plans = {
  list: (params: Record<string, unknown>) => api.get<Paginated<SanctionedPlan>>("/sanctioned-plans/", { params }).then((r) => r.data),
  get: (id: number) => api.get<SanctionedPlan>(`/sanctioned-plans/${id}/`).then((r) => r.data),
  byPid: (pid: string) => api.get<SanctionedPlan[]>(`/sanctioned-plans/by-pid/${encodeURIComponent(pid)}/`).then((r) => r.data),
  create: (d: Partial<SanctionedPlan>) => api.post<SanctionedPlan>("/sanctioned-plans/", d).then((r) => r.data),
  update: (id: number, d: Partial<SanctionedPlan>) => api.patch<SanctionedPlan>(`/sanctioned-plans/${id}/`, d).then((r) => r.data),
  bulkUpload: (fd: FormData) => api.post("/sanctioned-plans/bulk_upload/", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data as { created: number; updated: number; errors: { row: number; error: string }[] }),
  templateUrl: `${api.defaults.baseURL}/sanctioned-plans/template/`,
};
export const media = {
  upload: (fd: FormData, onProgress?: (p: number) => void) => api.post<Media>("/media/", fd, { headers: { "Content-Type": "multipart/form-data" }, onUploadProgress: (e) => onProgress?.(e.total ? Math.round((e.loaded / e.total) * 100) : 0) }).then((r) => r.data),
};
export const cases = {
  list: (params: Record<string, unknown>) => api.get<Paginated<CaseListItem>>("/cases/", { params }).then((r) => r.data),
  counts: () => api.get("/cases/counts/").then((r) => r.data as Record<string, number>),
  get: (id: string) => api.get<CaseDetail>(`/cases/${id}/`).then((r) => r.data),
  create: (d: Record<string, unknown>) => api.post<CaseDetail>("/cases/", d).then((r) => r.data),
  patch: (id: string, d: Record<string, unknown>) => api.patch<CaseDetail>(`/cases/${id}/`, d).then((r) => r.data),
  action: (id: string, action: string, d: Record<string, unknown> = {}) => api.post(`/cases/${id}/${action}/`, d).then((r) => r.data),
  timeline: (id: string) => api.get(`/cases/${id}/timeline/`).then((r) => r.data),
};
export const notices = {
  list: (params: Record<string, unknown>) => api.get<Paginated<Notice>>("/notices/", { params }).then((r) => r.data),
  get: (id: string) => api.get<Notice>(`/notices/${id}/`).then((r) => r.data),
  pdfUrl: (id: string) => `${api.defaults.baseURL}/notices/${id}/pdf/`,
  resendSms: (id: string, mobiles: string[] = []) => api.post(`/notices/${id}/resend_sms/`, { mobiles }).then((r) => r.data),
  resign: (id: string) => api.post<Notice>(`/notices/${id}/resign/`).then((r) => r.data),
  // public endpoint lives beside the API prefix (/building-violations/public/...); baseURL is cleared so axios does not prepend it
  verifyPublic: (code: string, h?: string) => api.get(`${API_BASE.replace(/\/api\/?$/, "")}/public/verify/${code}/`, { baseURL: "", params: h ? { h } : {} }).then((r) => r.data),
};
export const dashboards = {
  summary: (p: Record<string, unknown>) => api.get("/dashboards/summary/", { params: p }).then((r) => r.data as Record<string, number>),
  funnel: (p: Record<string, unknown>) => api.get("/dashboards/funnel/", { params: p }).then((r) => r.data as { status: string; label: string; count: number }[]),
  byArea: (p: Record<string, unknown>) => api.get("/dashboards/by-area/", { params: p }).then((r) => r.data as any[]),
  mix: (p: Record<string, unknown>) => api.get("/dashboards/violation-mix/", { params: p }).then((r) => r.data as any),
  ageing: (p: Record<string, unknown>) => api.get("/dashboards/ageing/", { params: p }).then((r) => r.data as any),
  sla: (p: Record<string, unknown>) => api.get("/dashboards/sla/", { params: p }).then((r) => r.data as any),
  officers: (p: Record<string, unknown>) => api.get("/dashboards/officers/", { params: p }).then((r) => r.data as any),
  trends: (p: Record<string, unknown>) => api.get("/dashboards/trends/", { params: p }).then((r) => r.data as any[]),
  map: (p: Record<string, unknown>) => api.get("/dashboards/map/", { params: p }).then((r) => r.data as any),
  deadlines: (p: Record<string, unknown>) => api.get("/dashboards/deadlines/", { params: p }).then((r) => r.data as any),
};
export const reports = {
  list: () => api.get("/reports/").then((r) => r.data as { name: string; title: string }[]),
  run: (name: string, p: Record<string, unknown>) => api.get(`/reports/${name}/`, { params: p }).then((r) => r.data as { columns: string[]; rows: unknown[][]; count: number }),
  downloadUrl: (name: string, fmt: "csv" | "xlsx", p: Record<string, unknown>) => `${api.defaults.baseURL}/reports/${name}/?export=${fmt}&${new URLSearchParams(p as any).toString()}`,
};
export const notificationsApi = {
  list: () => api.get<Paginated<Notification>>("/notifications/", { params: { page_size: 50 } }).then((r) => r.data),
  markRead: (ids?: number[]) => api.post("/notifications/mark_read/", { ids }).then((r) => r.data),
};
export const officers = {
  list: (params?: Record<string, unknown>) => api.get("/officers/", { params: { page_size: 200, ...params } }).then((r) => r.data as Paginated<any>),
  create: (d: Record<string, unknown>) => api.post("/officers/", d).then((r) => r.data),
  update: (id: number, d: Record<string, unknown>) => api.patch(`/officers/${id}/`, d).then((r) => r.data),
};
export const branches = {
  list: () => api.get<Branch[]>("/branches/").then((r) => r.data),
  save: (d: Partial<Branch> & { order_reference?: string }) => (d.code && d.code.length ? api.patch<Branch>(`/branches/${d.code}/`, d).then((r) => r.data) : api.post<Branch>("/branches/", d).then((r) => r.data)),
  create: (d: Partial<Branch> & { order_reference?: string }) => api.post<Branch>("/branches/", d).then((r) => r.data),
};
export const referrals = {
  list: (params: Record<string, unknown>) => api.get<Paginated<Referral>>("/referrals/", { params }).then((r) => r.data),
  counts: () => api.get("/referrals/counts/").then((r) => r.data as { pending: number; overdue: number; responded: number }),
};
export const admin = {
  rules: () => api.get<RulesMatrix>("/admin/workflow-rules/").then((r) => r.data),
  saveRules: (rules: { status: string; role: string; action: string; allowed: boolean }[], order_reference: string, remarks = "") => api.put<RulesMatrix>("/admin/workflow-rules/", { rules, order_reference, remarks }).then((r) => r.data),
  resetRules: (order_reference: string) => api.post<RulesMatrix>("/admin/workflow-rules/", { order_reference }).then((r) => r.data),
  settings: () => api.get<WorkflowSetting[]>("/admin/settings/").then((r) => r.data),
  saveSettings: (values: Record<string, unknown>, order_reference: string) => api.put<WorkflowSetting[]>("/admin/settings/", { values, order_reference }).then((r) => r.data),
  permissions: () => api.get<PermMatrix>("/admin/permissions/").then((r) => r.data),
  savePermissions: (grants: { role: string; permission: string; allowed: boolean }[], order_reference: string) => api.put<PermMatrix>("/admin/permissions/", { grants, order_reference }).then((r) => r.data),
  officerOverrides: (id: number) => api.get(`/officers/${id}/permissions/`).then((r) => r.data as { overrides: { permission: string; allowed: boolean; reason: string }[]; effective: string[]; role_defaults: string[] }),
  saveOfficerOverrides: (id: number, overrides: { permission: string; allowed: boolean; reason?: string }[], order_reference: string) => api.put(`/officers/${id}/permissions/`, { overrides, order_reference }).then((r) => r.data),
  auditLog: (params?: Record<string, string>) => api.get<AdminLog[]>("/admin/audit-log/", { params }).then((r) => r.data),
  reassign: (d: Record<string, unknown>) => api.post("/admin/reassign-cases/", d).then((r) => r.data as { reassigned: number }),
};
export type { Appeal };

export const integrity = {
  summary: () => api.get("/integrity/checks/summary/").then((r) => r.data as { rejected: number; flagged: number; passed: number; reasons: { code: string; text: string; count: number }[]; repeat_offenders: { officer: string; rejections: number }[] }),
  list: (p: Record<string, unknown>) => api.get("/integrity/checks/", { params: p }).then((r) => r.data),
};

/** Orders issued before the system (paper demolition / sealing / eviction orders) - backend services/legacy.py */
export const legacy = {
  list: (params: Record<string, unknown>) => api.get<Paginated<CaseListItem>>("/legacy-orders/", { params }).then((r) => r.data),
  create: (d: Record<string, unknown>) => api.post<CaseDetail>("/legacy-orders/", d).then((r) => r.data),
  updateStatus: (caseId: string, d: Record<string, unknown>) => api.post<CaseDetail>(`/legacy-orders/${caseId}/status/`, d).then((r) => r.data),
  summary: () => api.get("/legacy-orders/summary/").then((r) => r.data as { total: number; open: number; execution_due: number; stayed: number; by_status: Record<string, number>; batches: number }),
  batches: () => api.get("/legacy-orders/batches/").then((r) => r.data as { id: number; title: string; created_at: string; created_by: { name: string } | null; total_rows: number; imported: number; errors: { row: number; order_no: string; error: string }[] }[]),
  bulk: (fd: FormData) => api.post("/legacy-orders/bulk/", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data),
  templateUrl: `${api.defaults.baseURL}/legacy-orders/template/`,
};
