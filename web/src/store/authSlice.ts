/**
 * Auth / session state - Redux Toolkit slice persisted with redux-persist, as in the MCG platform portal.
 * Holds the JWT pair and the current officer (`/users/me/`). The Axios client reads the tokens from here
 * (see api/client.ts); the platform's own login can hydrate the same slice when the module is mounted inside it.
 */
import { createAsyncThunk, createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { Me } from "@/api/types";
import { auth as authApi } from "@/api/endpoints";

export interface AuthState { accessToken: string | null; refreshToken: string | null; user: Me | null; loading: boolean; }

const initialState: AuthState = { accessToken: null, refreshToken: null, user: null, loading: true };

/** Load (or re-validate) the current officer from the API using the persisted token. */
export const loadMe = createAsyncThunk<Me | null, void, { state: { auth: AuthState } }>("auth/loadMe", async (_, { getState }) => {
  if (!getState().auth.accessToken) return null;
  try { return await authApi.me(); } catch { return null; }
});

const slice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setTokens(state, action: PayloadAction<{ access: string; refresh: string; user: Me }>) {
      state.accessToken = action.payload.access;
      state.refreshToken = action.payload.refresh;
      state.user = action.payload.user;
      state.loading = false;
    },
    setAccessToken(state, action: PayloadAction<string>) { state.accessToken = action.payload; },
    setUser(state, action: PayloadAction<Me | null>) { state.user = action.payload; state.loading = false; },
    logout(state) { state.accessToken = null; state.refreshToken = null; state.user = null; state.loading = false; },
  },
  extraReducers: (b) => {
    b.addCase(loadMe.pending, (state) => { state.loading = true; });
    b.addCase(loadMe.fulfilled, (state, action) => {
      state.user = action.payload;
      state.loading = false;
      if (!action.payload) { state.accessToken = null; state.refreshToken = null; }
    });
    b.addCase(loadMe.rejected, (state) => { state.user = null; state.loading = false; });
  },
});

export const { setTokens, setAccessToken, setUser, logout } = slice.actions;
export default slice.reducer;
