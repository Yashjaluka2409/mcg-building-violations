/** Redux store (Redux Toolkit) with redux-persist for the auth/session slice - the platform portal's arrangement. */
import { combineReducers, configureStore } from "@reduxjs/toolkit";
import { FLUSH, PAUSE, PERSIST, PURGE, REGISTER, REHYDRATE, persistReducer, persistStore } from "redux-persist";
import storage from "redux-persist/lib/storage";
import { bindAuthBridge } from "@/api/client";
import authReducer, { logout, setAccessToken } from "./authSlice";

const rootReducer = combineReducers({ auth: authReducer });
const persistedReducer = persistReducer({ key: "bvms", version: 1, storage, whitelist: ["auth"] }, rootReducer);

export const store = configureStore({
  reducer: persistedReducer,
  middleware: (getDefault) => getDefault({ serializableCheck: { ignoredActions: [FLUSH, REHYDRATE, PAUSE, PERSIST, PURGE, REGISTER] } }),
});
export const persistor = persistStore(store);

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

// The Axios interceptors read/refresh tokens through this bridge (avoids a store <-> client import cycle).
bindAuthBridge({
  getAccess: () => store.getState().auth.accessToken,
  getRefresh: () => store.getState().auth.refreshToken,
  setAccess: (t) => store.dispatch(setAccessToken(t)),
  clear: () => store.dispatch(logout()),
});
