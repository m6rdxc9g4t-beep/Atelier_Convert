/** Mise en forme française des valeurs affichées (montants, dates, tailles). */

import type { CellValue, ColumnType } from "../types/convert";

const money = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" });
const number = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 10 });

/** 1234.5 → « 1 234,50 € ». */
export function formatMoney(value: number): string {
  return money.format(value);
}

/** « 2026-03-15 » → « 15/03/2026 » (texte inchangé sinon). */
export function formatDate(value: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : value;
}

/** Valeur d'une cellule telle qu'affichée dans l'aperçu. */
export function formatCell(value: CellValue, type: ColumnType): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "Oui" : "Non";
  if (typeof value === "number") return type === "currency" ? formatMoney(value) : number.format(value);
  if (type === "date") return formatDate(value);
  return value;
}

/** Texte proposé pour corriger une cellule : « 1234,5 », « 15/03/2026 », « Oui » — sans symbole ni espace de milliers. */
export function editText(value: CellValue, type: ColumnType): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "Oui" : "Non";
  if (typeof value === "number") return String(value).replace(".", ",");
  if (type === "date") return formatDate(value);
  return value;
}

/** Vrai si une valeur de colonne typée n'a pas pu être convertie (gardée en texte). */
export function unconverted(value: CellValue, type: ColumnType): boolean {
  if (value === null || value === undefined) return false;
  if (type === "number" || type === "currency") return typeof value !== "number";
  if (type === "date") return typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value);
  if (type === "boolean") return typeof value !== "boolean";
  return false;
}

/** 1536 → « 1,5 Ko ». */
export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Ko`;
  return `${(bytes / 1024 / 1024).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Mo`;
}

/** Horodatage ISO → « 22/10/2026 à 20:15 ». */
export function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toLocaleDateString("fr-FR")} à ${d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
}

export const TYPE_LABELS: Record<ColumnType, string> = {
  text: "Texte",
  number: "Nombre",
  currency: "Montant (€)",
  date: "Date",
  boolean: "Oui / non",
};

export const KIND_LABELS: Record<string, string> = {
  pdf: "PDF",
  image: "Image",
  csv: "CSV",
  txt: "TXT",
  xlsx: "Excel",
  xls: "Excel 97",
  ofx: "OFX",
  qif: "QIF",
  json: "JSON",
};
