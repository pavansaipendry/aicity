import { defineConfig } from "vite";
import path from "path";

/**
 * Vite config for AIcity Phase 6 isometric client.
 *
 * Dev server runs on port 5173.
 * Proxy rules:
 *   /ws  → ws://localhost:8000/ws   (WebSocket events from Python simulation)
 *   /api → http://localhost:8000    (REST endpoints: /api/world, /api/state …)
 *
 * Why proxy instead of direct URLs?
 * During development we have two servers (Vite:5173, FastAPI:8000).
 * Proxying makes the browser see one origin — avoids CORS headers entirely.
 * In production the FastAPI server serves the built static files directly,
 * so the proxy is only active during `npm run dev`.
 */
export default defineConfig({
  root: ".",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "../src/dashboard/static/game-v2-dist",
    emptyOutDir: true,
  },
});
