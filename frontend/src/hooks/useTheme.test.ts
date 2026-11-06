import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { applyThemeMarkers, useTheme } from "./useTheme";

describe("thème de l'application (docs/SUITE.md §1.5)", () => {
  afterEach(() => {
    localStorage.clear();
    window.atelierTheme?.set("system");
  });

  it("pose la classe dark ET data-theme", () => {
    const root = document.createElement("html");
    applyThemeMarkers("dark", root);
    expect(root.classList.contains("dark")).toBe(true);
    expect(root.getAttribute("data-theme")).toBe("dark");
    applyThemeMarkers("light", root);
    expect(root.classList.contains("dark")).toBe(false);
    expect(root.getAttribute("data-theme")).toBe("light");
  });

  it("passe par la préférence commune à la suite (window.atelierTheme, localStorage « atelier:theme »)", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setPreference("dark"));
    expect(localStorage.getItem("atelier:theme")).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(result.current.preference).toBe("dark");
    expect(result.current.theme).toBe("dark");

    // Changement fait ailleurs (une autre vue, une autre app) : le hook suit l'événement « atelier-theme ».
    act(() => window.atelierTheme?.set("light"));
    expect(result.current.preference).toBe("light");
    expect(result.current.theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
