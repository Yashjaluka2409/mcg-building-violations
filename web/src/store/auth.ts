/**
 * `useAuth()` - the hook every page uses. Backed by the Redux auth slice (see authSlice.ts); the selector
 * form `useAuth((s) => s.user)` is kept so existing screens did not have to change.
 */
import { useMemo } from "react";
import { useDispatch, useSelector } from "react-redux";
import type { Me } from "@/api/types";
import type { AppDispatch, RootState } from "./index";
import { loadMe, logout as logoutAction, setTokens as setTokensAction } from "./authSlice";

export interface AuthApi {
  user: Me | null;
  loading: boolean;
  accessToken: string | null;
  load: () => Promise<void>;
  setTokens: (access: string, refresh: string, user: Me) => void;
  logout: () => void;
}

export function useAuth(): AuthApi;
export function useAuth<T>(selector: (s: AuthApi) => T): T;
export function useAuth<T>(selector?: (s: AuthApi) => T) {
  const dispatch = useDispatch<AppDispatch>();
  const state = useSelector((s: RootState) => s.auth);
  const api = useMemo<AuthApi>(() => ({
    user: state.user,
    loading: state.loading,
    accessToken: state.accessToken,
    load: async () => { await dispatch(loadMe()); },
    setTokens: (access, refresh, user) => { dispatch(setTokensAction({ access, refresh, user })); },
    logout: () => { dispatch(logoutAction()); },
  }), [state.user, state.loading, state.accessToken, dispatch]);
  return selector ? selector(api) : api;
}
