import { describe, expect, it } from "vitest";

import { fileNameFrom } from "./api";
import { formatCell, formatDate, formatSize, unconverted } from "./format";
import { parseRoute } from "./router";

describe("mise en forme française", () => {
  it("montants, dates, booléens, tailles", () => {
    expect(formatCell(-84.2, "currency").replace(/\s/g, " ")).toBe("-84,20 €");
    expect(formatCell(1234.5, "number").replace(/\s/g, " ")).toBe("1 234,5");
    expect(formatCell("2026-03-15", "date")).toBe("15/03/2026");
    expect(formatCell(true, "boolean")).toBe("Oui");
    expect(formatCell(null, "text")).toBe("");
    expect(formatDate("15 mars")).toBe("15 mars");
    expect(formatSize(1536)).toBe("1,5 Ko");
  });

  it("repère les valeurs qui n'ont pas pu être converties", () => {
    expect(unconverted("n/a", "currency")).toBe(true);
    expect(unconverted(12, "currency")).toBe(false);
    expect(unconverted("15/03", "date")).toBe(true);
    expect(unconverted("2026-03-15", "date")).toBe(false);
    expect(unconverted(null, "number")).toBe(false);
  });
});

describe("nom des fichiers téléchargés", () => {
  it("préfère filename* (UTF-8)", () => {
    expect(fileNameFrom(`attachment; filename="Relev mars.csv"; filename*=UTF-8''Relev%C3%A9%20mars.csv`, "x")).toBe("Relevé mars.csv");
    expect(fileNameFrom('attachment; filename="a.csv"', "x")).toBe("a.csv");
    expect(fileNameFrom(null, "conversion.csv")).toBe("conversion.csv");
  });
});

describe("routeur", () => {
  it("lit les adresses", () => {
    expect(parseRoute("")).toEqual({ name: "convert", id: null });
    expect(parseRoute("#/conversions/0123456789ab")).toEqual({ name: "convert", id: "0123456789ab" });
    expect(parseRoute("#/conversions/../x")).toEqual({ name: "convert", id: null });
    expect(parseRoute("#/historique")).toEqual({ name: "history" });
    expect(parseRoute("#/reglages")).toEqual({ name: "settings" });
  });
});
