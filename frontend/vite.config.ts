/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // docs/SUITE.md §2 : 127.0.0.1:5176, échec explicite si le port est pris.
  server: {
    host: "127.0.0.1",
    port: 5176,
    strictPort: true,
    // Le front appelle /api/... ; Vite relaie vers FastAPI (pas de CORS en dev).
    // `changeOrigin: false` : les en-têtes Host (127.0.0.1:5176) et Origin d'origine arrivent tels quels
    // au garde « requêtes locales » de l'API (backend/app/core/local_only.py), qui les accepte.
    proxy: { "/api": { target: "http://127.0.0.1:8010", changeOrigin: false } },
  },
  preview: { host: "127.0.0.1", port: 4176, strictPort: true, proxy: { "/api": { target: "http://127.0.0.1:8010", changeOrigin: false } } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
