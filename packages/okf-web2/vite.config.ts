/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig } from "vite";

// Dev: `uv run okf-web` serves the API on 8765; Vite proxies /api to it.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // OKF_API overrides the backend, e.g. to point at a slow proxy when testing loading states.
  // Two pages: the app (index.html) and the landing page (landing.html).
  build: { rollupOptions: { input: { app: resolve(__dirname, "index.html"), landing: resolve(__dirname, "landing.html") } } },
  server: { port: 5173, proxy: { "/api": process.env.OKF_API ?? "http://127.0.0.1:8765" } },
  test: {
    environment: "happy-dom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    globals: true,
  },
});
