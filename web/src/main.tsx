import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Provider } from "react-redux";
import { PersistGate } from "redux-persist/integration/react";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { persistor, store } from "./store";
import "./index.css";
import "./i18n";

// Standalone dev convenience: opening http://localhost:5173/ lands on the module prefix.
const BASENAME = import.meta.env.VITE_ROUTER_BASENAME || "/building-violations";
if (window.location.pathname === "/" && BASENAME !== "/") window.history.replaceState(null, "", BASENAME + "/");

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false } } });

// Provider order matches the platform portal: Redux (persisted auth/session) -> React Query -> Router.
// The module is mounted at /building-violations inside the MCG portal; when served standalone
// (vite dev) the same prefix is used so links and the QR verification URL behave identically.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Provider store={store}>
      <PersistGate loading={null} persistor={persistor}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter basename={BASENAME}>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </PersistGate>
    </Provider>
  </React.StrictMode>,
);
