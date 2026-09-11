import { api } from "./client";

export const auth = {
  requestOtp: (mobile: string) => api.post("/auth/otp/request/", { mobile }).then((r) => r.data),
  verifyOtp: (mobile: string, otp: string, device_id: string) => api.post("/auth/otp/verify/", { mobile, otp, device_id }).then((r) => r.data),
  me: () => api.get("/users/me/").then((r) => r.data),
};
export const masters = {
  violationTypes: () => api.get("/masters/violation-types/").then((r) => r.data),
  wards: () => api.get("/masters/wards/").then((r) => r.data),
  orderTypes: () => api.get("/masters/order-types/").then((r) => r.data),
  workflowConfig: () => api.get("/masters/workflow-config/").then((r) => r.data),
};
export const property = {
  lookupPid: (pid: string) => api.get(`/property/pid/${encodeURIComponent(pid)}/`).then((r) => r.data),
  checkPoint: (lat: number, lng: number) => api.get("/gis/check-point/", { params: { lat, lng } }).then((r) => r.data),
  govtLand: (bbox?: string) => api.get("/gis/govt-land/geojson/", { params: bbox ? { bbox } : {} }).then((r) => r.data),
};
export const plans = { byPid: (pid: string) => api.get(`/sanctioned-plans/by-pid/${encodeURIComponent(pid)}/`).then((r) => r.data), create: (d: any) => api.post("/sanctioned-plans/", d).then((r) => r.data) };
export const cases = {
  list: (params: any) => api.get("/cases/", { params }).then((r) => r.data),
  counts: () => api.get("/cases/counts/").then((r) => r.data),
  get: (id: string) => api.get(`/cases/${id}/`).then((r) => r.data),
  create: (d: any) => api.post("/cases/", d).then((r) => r.data),
  action: (id: string, action: string, d: any = {}) => api.post(`/cases/${id}/${action}/`, d).then((r) => r.data),
};
export const notices = { pdfPath: (id: string) => `/notices/${id}/pdf/` };
export const notificationsApi = { list: () => api.get("/notifications/", { params: { page_size: 50 } }).then((r) => r.data), markRead: () => api.post("/notifications/mark_read/", {}).then((r) => r.data) };
export const dashboards = { summary: () => api.get("/dashboards/summary/").then((r) => r.data), deadlines: () => api.get("/dashboards/deadlines/", { params: { days: 7 } }).then((r) => r.data) };
