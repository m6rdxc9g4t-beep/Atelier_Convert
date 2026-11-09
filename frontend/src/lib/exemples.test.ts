import { describe, expect, it } from "vitest";

import type { ExempleHistoire } from "../types/convert";
import { pickHistoire, readRemembered, remember, stepsAround } from "./exemples";

const apps = ["convert", "tab", "viz", "tresorerie", "nexus", "projets", "wiki"] as const;
const h = (id: string): ExempleHistoire => ({
  id,
  titre: id,
  sous_titre: "",
  secteur: "",
  resume: "",
  parcours: apps.map((app) => ({ app, titre: `Étape ${app}`, texte: "" })),
  fichiers: [],
  tab_projet: "Compta 2026",
});

describe("exemples de la suite", () => {
  it("trouve l'étape courante et la suivante", () => {
    const s = stepsAround(h("a"));
    expect(s.index).toBe(0);
    expect(s.current?.app).toBe("convert");
    expect(s.next?.app).toBe("tab");
    expect(stepsAround(h("a"), "wiki").next).toBeNull();
  });

  it("reprend l'histoire mémorisée, sinon la première", () => {
    const list = [h("a"), h("b")];
    expect(pickHistoire(list, "b")?.id).toBe("b");
    expect(pickHistoire(list, "disparue")?.id).toBe("a");
    expect(pickHistoire([], null)).toBeNull();
  });

  it("supporte un stockage absent ou en erreur", () => {
    const broken = {
      getItem: () => {
        throw new Error("interdit");
      },
      setItem: () => {
        throw new Error("interdit");
      },
    };
    expect(readRemembered(broken)).toBeNull();
    expect(() => remember("a", broken)).not.toThrow();
    const map = new Map<string, string>();
    remember("b", { setItem: (k, v) => void map.set(k, v) });
    expect(readRemembered({ getItem: (k) => map.get(k) ?? null })).toBe("b");
  });
});
