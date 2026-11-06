/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { type Plugin, defineConfig } from "vite";

/**
 * Préférence de thème commune à la suite (docs/SUITE.md §1.5) : la copie verbatim de `atelier-theme.js` est
 * insérée telle quelle en tête de <head>, en script bloquant, pour poser le thème avant le premier affichage
 * (en développement comme dans `dist/`, sans fichier à servir à part).
 */
function atelierTheme(): Plugin {
  const file = new URL("./src/styles/atelier-brand/atelier-theme.js", import.meta.url);
  return {
    name: "atelier-theme",
    transformIndexHtml: () => [{ tag: "script", children: readFileSync(file, "utf8"), injectTo: "head-prepend" }],
  };
}

export default defineConfig({
  plugins: [atelierTheme(), react(), tailwindcss()],
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
