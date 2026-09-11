/**
 * Axios client with the MCG platform's conventions:
 *  - Bearer access token injected by a request interceptor; on 401 the refresh token is exchanged once
 *    (`/auth/token/refresh/`, body {refresh} -> {access}) and the request replayed
 *  - errors arrive as {detail: "..."}
 * Tokens live in the persisted Redux auth slice (store/authSlice.ts) and reach this module through
 * `bindAuthBridge`, so the platform's own session can drive the module when it is mounted inside the portal.
 * VITE_API_BASE points at the backend (e.g. https://sms-be.austere.biz/building-violations/api).
 */
import axios, { AxiosError } from "axios";

export const API_BASE = import.meta.env.VITE_API_BASE || "/building-violations/api";

export interface AuthBridge { getAccess: () => string | null; getRefresh: () => string | null; setAccess: (t: string) => void; clear: () => void; }
let bridge: AuthBridge = {
  getAccess: () => localStorage.getItem("accessToken"),
  getRefresh: () => localStorage.getItem("refreshToken"),
  setAccess: (t) => localStorage.setItem("accessToken", t),
  clear: () => { localStorage.removeItem("accessToken"); localStorage.removeItem("refreshToken"); },
};
export function bindAuthBridge(b: AuthBridge) { bridge = b; }

export const api = axios.create({ baseURL: API_BASE, timeout: 60_000 });

api.interceptors.request.use((cfg) => {
  const t = bridge.getAccess();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  cfg.headers["X-Device-Id"] = deviceId();
  return cfg;
});

let refreshing: Promise<string | null> | null = null;
api.interceptors.response.use(
  (r) => r,
  async (err: AxiosError<any>) => {
    const original: any = err.config;
    const refresh = bridge.getRefresh();
    if (err.response?.status === 401 && !original?._retry && refresh) {
      original._retry = true;
      refreshing ??= axios
        .post(`${API_BASE}/auth/token/refresh/`, { refresh })
        .then((r) => { bridge.setAccess(r.data.access); return r.data.access as string; })
        .catch(() => { bridge.clear(); window.location.reload(); return null; })
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
