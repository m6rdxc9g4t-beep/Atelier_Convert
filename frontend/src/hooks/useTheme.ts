import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";
export type ThemePreference = Theme | "system";

/** Ancienne clé (avant la préférence commune à la suite) : reprise une fois, puis supprimée. */
const LEGACY_KEY = "theme";

/**
 * Pose les deux marqueurs du thème sur <html> (docs/SUITE.md §1.5) : classe `dark` (variantes Tailwind)
 * et `data-theme` (jetons de la marque et du design system).
 */
export function applyThemeMarkers(theme: Theme, root: HTMLElement = document.documentElement): void {
  root.classList.toggle("dark", theme === "dark");
  root.setAttribute("data-theme", theme);
}

const api = () => (typeof window !== "undefined" ? window.atelierTheme : undefined);

function readPreference(): ThemePreference {
  return api()?.get() ?? "system";
}

function readTheme(): Theme {
  return api()?.resolved() ?? (document.documentElement.classList.contains("dark") ? "dark" : "light");
}

/** Choix mémorisé par une version précédente de Convert (localStorage « theme ») : repris dans la préférence commune. */
function migrateLegacy(): void {
  try {
    const old = localStorage.getItem(LEGACY_KEY);
    if (old === null) return;
    localStorage.removeItem(LEGACY_KEY);
    if ((old === "light" || old === "dark") && localStorage.getItem("atelier:theme") === null) api()?.set(old);
  } catch {
    /* stockage indisponible (navigation privée) */
  }
}
if (typeof window !== "undefined") migrateLegacy();

/**
 * Thème de l'application : clair, sombre ou « système » (suit macOS / Windows).
 * Préférence commune à la suite (`window.atelierTheme`, styles/atelier-brand/atelier-theme.js) : cookie de la suite
 * sur le VPS, sinon mémorisée sur cette machine. Suit les changements faits ailleurs (événement « atelier-theme »,
 * thème du système, retour sur l'onglet).
 */
export function useTheme(): {
  theme: Theme;
  preference: ThemePreference;
  setPreference: (p: ThemePreference) => void;
  toggle: () => void;
} {
  const [preference, setPref] = useState<ThemePreference>(readPreference);
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    const sync = () => {
      setPref(readPreference());
      setTheme(readTheme());
    };
    // atelier-theme.js réapplique le thème du système ou celui d'un autre onglet sans émettre d'événement :
    // on observe donc aussi <html>.
    const observer = new MutationObserver(sync);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-theme-pref"] });
    window.addEventListener("atelier-theme", sync);
    sync();
    return () => {
      observer.disconnect();
      window.removeEventListener("atelier-theme", sync);
    };
  }, []);

  const setPreference = useCallback((p: ThemePreference) => {
    const theme = api();
    if (theme) theme.set(p);
    else applyThemeMarkers(p === "system" ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : p);
  }, []);

  const toggle = useCallback(() => setPreference(readTheme() === "dark" ? "light" : "dark"), [setPreference]);

  return { theme, preference, setPreference, toggle };
}
