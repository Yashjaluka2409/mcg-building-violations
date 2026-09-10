import { create } from "zustand";
import { auth } from "@/api/endpoints";
import { clearTokens, getToken, setTokens } from "@/api/client";

interface S { user: any | null; loading: boolean; load: () => Promise<void>; login: (a: string, r: string, u: any) => Promise<void>; logout: () => Promise<void>; }
export const useAuth = create<S>((set) => ({
  user: null, loading: true,
  load: async () => { if (!(await getToken("accessToken"))) return set({ user: null, loading: false }); try { set({ user: await auth.me(), loading: false }); } catch { set({ user: null, loading: false }); } },
  login: async (a, r, u) => { await setTokens(a, r); set({ user: u, loading: false }); },
  logout: async () => { await clearTokens(); set({ user: null }); },
}));
