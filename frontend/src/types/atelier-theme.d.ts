/** Préférence de thème commune à la suite (styles/atelier-brand/atelier-theme.js, docs/SUITE.md §1.5). */
type AtelierThemePreference = "system" | "light" | "dark";

interface AtelierThemeApi {
  /** Préférence enregistrée (cookie de la suite sur le VPS, sinon localStorage « atelier:theme »). */
  get(): AtelierThemePreference;
  /** Enregistre et applique la préférence ; émet l'événement « atelier-theme ». */
  set(pref: AtelierThemePreference): void;
  /** Thème effectivement affiché. */
  resolved(): "light" | "dark";
}

interface Window {
  atelierTheme?: AtelierThemeApi;
}

interface WindowEventMap {
  "atelier-theme": CustomEvent<AtelierThemePreference>;
}
