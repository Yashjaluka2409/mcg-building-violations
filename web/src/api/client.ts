/**
 * Axios client with the same conventions as the MCG platform:
 *  - Bearer access token from localStorage("accessToken"), refresh via refresh_token
 *  - errors arrive as {detail: "..."}
 * When mounted inside the platform, point VITE_API_BASE at sms-be (e.g. https://sms-be.austere.biz/building-violations/api)
 * and the platform's login already provides the tokens - nothing else changes.
 */
import axios, { AxiosError } from "axios";

export const API_BASE = import.meta.env.VITE_API_BASE || "/building-violations/api";

export const api = axios.create({ baseURL: API_BASE, timeout: 60_000 });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("accessToken");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  cfg.headers["X-Device-Id"] = deviceId();
  return cfg;
});

let refreshing: Promise<string | null> | null = null;
api.interceptors.response.use(
  (r) => r,
  async (err: AxiosError<any>) => {
    const original: any = err.config;
    if (err.response?.status === 401 && !original?._retry && localStorage.getItem("refreshToken")) {
      original._retry = true;
      refreshing ??= axios
        .post(`${API_BASE}/auth/token/refresh/`, { refresh: localStorage.getItem("refreshToken") })
        .then((r) => { localStorage.setItem("accessToken", r.data.access); return r.data.access as string; })
        .catch(() => { localStorage.removeItem("accessToken"); localStorage.removeItem("refreshToken"); window.location.reload(); return null; })
        .finally(() => { refreshing = null; });
      const token = await refreshing;
      if (token) { original.headers.Authorization = `Bearer ${token}`; return api(original); }
    }
    return Promise.reject(err);
  },
);

export function errorMessage(e: unknown): string {
  const ax = e as AxiosError<any>;
  const d = ax?.response?.data;
  if (!d) return ax?.message || "Request failed";
  if (typeof d === "string") return d;
  if (d.detail) return String(d.detail);
  const first = Object.entries(d)[0];
  if (first) return `${first[0]}: ${Array.isArray(first[1]) ? first[1].join(", ") : JSON.stringify(first[1])}`;
  return "Request failed";
}

export function deviceId(): string {
  let id = localStorage.getItem("bvmsDeviceId");
  if (!id) { id = `web-${Math.random().toString(36).slice(2, 10)}`; localStorage.setItem("bvmsDeviceId", id); }
  return id;
}

export const absoluteMedia = (url?: string | null) => (url ? url : undefined);
