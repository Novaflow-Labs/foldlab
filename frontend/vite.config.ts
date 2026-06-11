import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: serve the SPA on :5173 and proxy /api to the FastAPI backend on :8000
// (same-origin in dev, so no CORS needed).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 127.0.0.1 (not "localhost") so the proxy hits uvicorn's IPv4 bind on
      // Windows/Node, where "localhost" can resolve to IPv6 ::1 first.
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
