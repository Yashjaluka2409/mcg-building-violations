import axios from "axios";
import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";
import * as Device from "expo-device";

import AsyncStorage from "@react-native-async-storage/async-storage";

// Same auth conventions as the MCG HARYANA app: Bearer access token + refresh token.
// The server URL can be changed on the login screen (stored on the device) so that testers can point
// the app at a sandbox / tunnel without rebuilding. Enter the portal origin, e.g. https://host:8000
export const DEFAULT_API_BASE = process.env.EXPO_PUBLIC_API_BASE || (Constants.expoConfig?.extra as any)?.apiBase || "http://127.0.0.1:8000/building-violations/api";
export let API_BASE = DEFAULT_API_BASE;
export const normaliseServer = (v: string) => { let u = v.trim().replace(/\/+$/, ""); if (!/^https?:\/\//.test(u)) u = "https://" + u; u = u.replace(/\/building-violations(\/api)?$/, ""); return u + "/building-violations/api"; };
export async function loadServer() { const v = await AsyncStorage.getItem("serverUrl"); if (v) { API_BASE = v; api.defaults.baseURL = v; } return API_BASE; }
export async function setServer(v: string) { const b = normaliseServer(v); await AsyncStorage.setItem("serverUrl", b); API_BASE = b; api.defaults.baseURL = b; return b; }
export const api = axios.create({ baseURL: API_BASE, timeout: 120_000 });

// Tokens live in the iOS Keychain / Android Keystore (expo-secure-store). Development builds signed without an Apple
// team have no keychain entitlement on the simulator; in that case (and only in __DEV__ builds) fall back to
// AsyncStorage so the app remains testable. Production builds never fall back.
async function secureGet(k: string) { try { return await SecureStore.getItemAsync(k); } catch (e) { if (__DEV__) return AsyncStorage.getItem(k); throw e; } }
async function secureSet(k: string, v: string) { try { await SecureStore.setItemAsync(k, v); } catch (e) { if (__DEV__) { await AsyncStorage.setItem(k, v); return; } throw e; } }
async function secureDelete(k: string) { try { await SecureStore.deleteItemAsync(k); } catch (e) { if (__DEV__) { await AsyncStorage.removeItem(k); return; } throw e; } }
export async function getToken(k: "accessToken" | "refreshToken") { try { return await secureGet(k); } catch { return null; } }
export async function setTokens(a: string, r: string) { await secureSet("accessToken", a); await secureSet("refreshToken", r); }
export async function clearTokens() { await secureDelete("accessToken"); await secureDelete("refreshToken"); }
export const deviceId = () => `${Device.modelName || "device"}-${Device.osBuildId || Device.osVersion || ""}`.slice(0, 100);

api.interceptors.request.use(async (cfg) => {
  const t = await getToken("accessToken");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  cfg.headers["X-Device-Id"] = deviceId();
  return cfg;
});
api.interceptors.response.use((r) => r, async (err) => {
  const original = err.config;
  const refresh = await getToken("refreshToken");
  if (err.response?.status === 401 && !original._retry && refresh) {
    original._retry = true;
    try {
      const r = await axios.post(`${api.defaults.baseURL}/auth/token/refresh/`, { refresh });
      await secureSet("accessToken", r.data.access);
      original.headers.Authorization = `Bearer ${r.data.access}`;
      return api(original);
    } catch { await clearTokens(); }
  }
  return Promise.reject(err);
});
export function errorMessage(e: any): string {
  const d = e?.response?.data;
  if (!d) return e?.message === "Network Error" ? "No network - saved offline, will sync later" : e?.message || "Request failed";
  if (typeof d === "string") return d;
  if (d.detail) return String(d.detail);
  const first = Object.entries(d)[0];
  return first ? `${first[0]}: ${Array.isArray(first[1]) ? first[1].join(", ") : JSON.stringify(first[1])}` : "Request failed";
}
