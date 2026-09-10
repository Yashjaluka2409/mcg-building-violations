import { create } from "zustand";
import type { Me } from "@/api/types";
import { auth } from "@/api/endpoints";

interface AuthState { user: Me | null; loading: boolean; load: () => Promise<void>; setTokens: (a: string, r: string, u: Me) => void; logout: () => void; }

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,
  load: async () => {
    if (!localStorage.getItem("accessToken")) { set({ user: null, loading: false }); return; }
    try { set({ user: await auth.me(), loading: false }); } catch { set({ user: null, loading: false }); }
  },
  setTokens: (a, r, u) => { localStorage.setItem("accessToken", a); localStorage.setItem("refreshToken", r); set({ user: u, loading: false }); },
  logout: () => { localStorage.removeItem("accessToken"); localStorage.removeItem("refreshToken"); set({ user: null }); },
}));
