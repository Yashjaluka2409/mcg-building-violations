import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// The module is served under /building-violations/ so that it can be mounted
// beside the other MCG platform modules (/cd-waste-admin, /challan, /gisportal ...).
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE_PATH || "/",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@shared": path.resolve(__dirname, "../shared/src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // dev only: forward the module's API, the public verify endpoint and media files to Django
      "/building-violations/api": { target: process.env.VITE_API_PROXY || "http://127.0.0.1:8000", changeOrigin: true },
      "/building-violations/public": { target: process.env.VITE_API_PROXY || "http://127.0.0.1:8000", changeOrigin: true },
      "/media": { target: process.env.VITE_API_PROXY || "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
