/// <reference types="node" />
// Lecture directe des fichiers : Vitest neutralise le CSS importé (même en `?raw`).
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const read = (name: string) => readFileSync(new URL(name, import.meta.url), "utf8");
const indexCss = read("../../index.css");
const colors = read("./colors.css");
const dark = read("./dark.css");
const light = read("./light.css");
const brand = read("../atelier-brand/atelier-brand.css");
const themeJs = read("../atelier-brand/atelier-theme.js");
const indexHtml = read("../../../index.html");
const viteConfig = read("../../../vite.config.ts");
const here = dirname(fileURLToPath(import.meta.url));
/** Source du design system (dépôt voisin `atelier_projets`), comparée quand elle est présente. */
const SOURCE = resolve(here, "../../../../../atelier_projets/design-system");
/** Copies verbatim : fichier de la source → copie dans Convert. */
const COPIES: [string, string][] = [
  ["brand/atelier-brand.css", "../atelier-brand/atelier-brand.css"],
  ["brand/atelier-theme.js", "../atelier-brand/atelier-theme.js"],
  ["brand/inter-latin-wght-normal.woff2", "../atelier-brand/inter-latin-wght-normal.woff2"],
  ["brand/inter-latin-ext-wght-normal.woff2", "../atelier-brand/inter-latin-ext-wght-normal.woff2"],
  ["brand/LICENSE-Inter.txt", "../atelier-brand/LICENSE-Inter.txt"],
  ["themes/light.css", "./light.css"],
  ["themes/dark.css", "./dark.css"],
  ["tokens/colors.css", "./colors.css"],
];

/** Variables déclarées dans une feuille (`--nom:`). */
const declared = (css: string) => new Set([...css.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]));

const FOUNDATION = ["--bg-main", "--bg-surface", "--bg-elevated", "--text-primary", "--text-muted", "--border-color"];
const OFFICIAL = {
  "--type-phase": "#FF8F2B",
  "--type-milestone": "#2A9A30",
  "--type-epic": "#8250DF",
  "--type-story": "#6F42C1",
  "--type-feature": "#2A9A30",
  "--type-task": "#1B66A3",
  "--type-bug": "#D64545",
  "--status-open": "#64748B",
  "--status-progress": "#2563EB",
  "--status-review": "#8B5CF6",
  "--status-hold": "#F59E0B",
  "--status-blocked": "#EA580C",
  "--status-resolved": "#0D9488",
  "--status-closed": "#16A34A",
  "--status-rejected": "#DC2626",
};

describe("design system de la Suite Atelier (copies verbatim, docs/SUITE.md §1.1)", () => {
  it("chaque copie commence par le commentaire d'origine", () => {
    for (const css of [light, dark, colors]) expect(css.trimStart().startsWith("/* ====")).toBe(true);
    expect(light).toContain("Atelier_Projets · Design System — Thème CLAIR");
    expect(dark).toContain("Atelier_Projets · Design System — Thème SOMBRE");
    expect(colors).toContain("Atelier_Projets · Design System — Tokens de couleurs officiels");
  });

  it("les deux thèmes déclarent les 6 variables de fondation", () => {
    for (const css of [light, dark]) {
      const vars = declared(css);
      for (const v of FOUNDATION) expect(vars.has(v), v).toBe(true);
    }
    expect(dark).toContain('[data-theme="dark"]');
  });

  it("les 15 couleurs officielles sont présentes avec leur code", () => {
    expect(Object.keys(OFFICIAL)).toHaveLength(15);
    for (const [name, hex] of Object.entries(OFFICIAL)) expect(colors).toMatch(new RegExp(`${name}:\\s*${hex};`));
  });

  it("index.css importe les copies ; l'habillage dérive des jetons --atelier-* de la marque (§1.2, §1.7)", () => {
    for (const f of ["colors.css", "light.css", "dark.css"]) expect(indexCss).toContain(`./styles/atelier-ds/${f}`);
    const map: [string, string][] = [
      ["--bg", "var(--atelier-bg)"],
      ["--sidebar", "var(--atelier-sidebar)"],
      ["--surface", "var(--atelier-surface)"],
      ["--surface-2", "var(--atelier-surface-2)"],
      ["--surface-3", "var(--atelier-surface-3)"],
      ["--field", "var(--atelier-field)"],
      ["--border", "var(--atelier-border-soft)"],
      ["--border-strong", "var(--atelier-border)"],
      ["--line", "var(--atelier-line)"],
      ["--fg", "var(--atelier-text)"],
      ["--muted", "var(--atelier-muted)"],
      ["--grid", "var(--atelier-line)"],
      ["--accent", "var(--atelier-signature)"],
      ["--accent-fg", "var(--atelier-signature-contrast)"],
      ["--accent-ink", "var(--atelier-ink)"],
      ["--accent-soft", "var(--atelier-signature-soft)"],
    ];
    for (const [token, value] of map) expect(indexCss).toContain(`${token}: ${value};`);
    // Données (montants, contrôles) : couleurs inchangées ; états anormaux de l'interface : jetons de la suite.
    expect(indexCss).toMatch(/--positive: color-mix\(in oklab, var\(--status-closed\)/);
    expect(indexCss).toMatch(/--negative: color-mix\(in oklab, var\(--status-rejected\)/);
    expect(indexCss).toContain("--warning: var(--atelier-warn);");
    expect(indexCss).toContain("--danger: var(--atelier-down);");
    // Inter embarquée par la marque (--atelier-font) ; aucune police déclarée ni téléchargée ici.
    expect(indexCss).toContain("--font-sans: var(--atelier-font);");
    expect(indexCss).not.toMatch(/@font-face|fonts\.googleapis|Inter Variable/);
  });

  it("charte v2 « Linear » : plat au repos, sans grille, lueur, halo ni texte lumineux (§1.7)", () => {
    expect(indexCss).not.toMatch(/--atelier-backdrop|--atelier-text-glow|--atelier-signature-glow|text-shadow|radial-gradient|filter:\s*brightness/);
    expect(indexCss).toMatch(/body \{\s*background: var\(--bg\);/);
    // Rayons 5 / 7 / 10 px.
    for (const [token, value] of [["--radius-sm", "5px"], ["--radius-md", "7px"], ["--radius-lg", "10px"]]) expect(indexCss).toContain(`${token}: ${value};`);
  });

  it("signature d'Atelier Convert : ocre #9d6d1c, déclarée par la marque commune (§1.7)", () => {
    expect(indexHtml).toMatch(/<html[^>]*data-atelier-app="convert"/);
    expect(brand).toMatch(/--atelier-sig-convert: #9d6d1c;/i);
    expect(brand).toContain('[data-atelier-app="convert"] { --atelier-signature: var(--atelier-sig-convert); }');
    // Plus de surcharge locale de la signature ni de son contraste (texte blanc, comme toute la suite).
    expect(indexCss).not.toMatch(/--atelier-sig-convert|--atelier-signature-contrast:/);
    // Jetons de la v1 (base cyan, bleu nuit) : plus aucun usage dans l'habillage.
    expect(indexCss).not.toMatch(/--atelier-(neon|night|glass|edge|signature-light)\b/);
    expect(indexCss).not.toMatch(/#06111f|#0a1b2e|#10283f|#17405c|#3fd8ff|#c9951d/i);
  });

  it("la marque commune définit la signature de chaque app du sélecteur de la suite (§1.7, §3)", () => {
    const signatures = { viz: "#996c00", tab: "#1c8742", convert: "#9d6d1c", projets: "#568100", cuisine: "#8568a7" };
    for (const [app, hex] of Object.entries(signatures)) {
      expect(brand).toMatch(new RegExp(`--atelier-sig-${app}: ${hex};`, "i"));
      expect(brand).toContain(`[data-atelier-app="${app}"] { --atelier-signature: var(--atelier-sig-${app});`);
    }
  });

  it("marque v2 : police Inter embarquée (plus de Nunito), préférence de thème commune posée avant l'affichage (§1.3, §1.5)", () => {
    expect(existsSync(resolve(here, "../atelier-brand/inter-latin-wght-normal.woff2"))).toBe(true);
    expect(existsSync(resolve(here, "../atelier-brand/inter-latin-ext-wght-normal.woff2"))).toBe(true);
    expect(existsSync(resolve(here, "../atelier-brand/nunito-latin-wght-normal.woff2"))).toBe(false);
    expect(brand).toContain('font-family: "Atelier Inter";');
    expect(themeJs).toContain("window.atelierTheme = {");
    // vite.config.ts insère la copie verbatim en tête de <head> ; plus d'ancien script de thème dans index.html.
    expect(viteConfig).toMatch(/atelier-brand\/atelier-theme\.js/);
    expect(viteConfig).toContain('injectTo: "head-prepend"');
    expect(indexHtml).not.toMatch(/localStorage|<script>/);
  });

  it.skipIf(!existsSync(SOURCE))("chaque copie est identique à l'octet près à celle d'Atelier Projets", () => {
    for (const [source, copy] of COPIES) {
      expect(readFileSync(resolve(here, copy)).equals(readFileSync(resolve(SOURCE, source))), copy).toBe(true);
    }
  });
});
