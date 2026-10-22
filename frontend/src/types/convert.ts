/** Miroir de backend/app/schemas/convert.py — garder synchronisé. */

import type { ProviderChoice, ProviderName } from "./ai";

export type ColumnType = "text" | "number" | "currency" | "date" | "boolean";
export type SourceKind = "pdf" | "image" | "csv" | "txt" | "xlsx" | "xls" | "ofx" | "qif" | "json";
export type PdfMode = "auto" | "statement" | "tables" | "text";
export type Profile = "auto" | "statement" | "raw";
export type Role = "date" | "value_date" | "label" | "debit" | "credit" | "amount" | "balance" | "reference" | "category";
export type ExportFormat = "csv-fr" | "csv" | "txt" | "xlsx" | "json";
export type CellValue = string | number | boolean | null;

export interface ParseOptions {
  pdf_mode: PdfMode;
  profile: Profile;
  delimiter: string | null;
  encoding: string | null;
  header: boolean | null;
  skip_rows: number;
  sheet: string | null;
  decimal: "auto" | "," | ".";
  date_order: "auto" | "dmy" | "mdy" | "ymd";
  pages: string | null;
  year: number | null;
  /** OCR d'un PDF : auto = seulement s'il n'a pas de texte (scanné). */
  ocr: "auto" | "always" | "never";
}

export interface Column {
  key: string;
  label: string;
  type: ColumnType;
  include: boolean;
  role: Role | null;
}

export interface StatementSummary {
  transactions: number;
  start: string | null;
  end: string | null;
  total_debit: number;
  total_credit: number;
  opening_balance: number | null;
  closing_balance: number | null;
  balance_check: "ok" | "mismatch" | "unknown";
  balance_gap: number | null;
  bank: string | null;
}

export interface SourceInfo {
  filename: string;
  kind: SourceKind;
  size: number;
  sha256: string;
  pages: number | null;
  encoding: string | null;
  delimiter: string | null;
  sheets: string[];
  ocr: boolean;
  ocr_confidence: number | null;
  ocr_languages: string | null;
}

export interface TabSend {
  at: string;
  table_id: string;
  table_name: string;
  project_id: string;
  project_name: string;
  rows: number;
}

export interface ConversionSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  source: SourceInfo;
  detected: string;
  rows: number;
  columns: number;
  statement: StatementSummary | null;
  sent: TabSend[];
}

export interface ConversionView extends ConversionSummary {
  options: ParseOptions;
  warnings: string[];
  table_columns: Column[];
  preview: Record<string, CellValue>[];
  preview_truncated: boolean;
  has_text: boolean;
}

export interface TabProject {
  id: string;
  name: string;
  workspace: string;
  tables: number;
}

export interface TabStatus {
  found: boolean;
  directory: string;
  projects: TabProject[];
  detail: string | null;
}

export interface SendToTabResult {
  table_id: string;
  table_name: string;
  project_id: string;
  project_name: string;
  rows: number;
  columns: number;
  file: string;
}

export interface StructureRequest {
  provider: ProviderChoice;
  instructions?: string | null;
}

export interface StructureResult {
  provider: ProviderName;
  model: string;
  sent_lines: number;
  sent_chars: number;
  conversion: ConversionView;
}

export interface SampleInfo {
  name: string;
  label: string;
  description: string;
}

export interface AppInfo {
  version: string;
  max_upload_mb: number;
  ai_max_lines: number;
  ai_max_chars: number;
  tab_directory: string;
  extensions: string[];
}

export const DEFAULT_OPTIONS: ParseOptions = {
  pdf_mode: "auto",
  profile: "auto",
  delimiter: null,
  encoding: null,
  header: null,
  skip_rows: 0,
  sheet: null,
  decimal: "auto",
  date_order: "auto",
  pages: null,
  year: null,
  ocr: "auto",
};

/** Miroir de `OcrStatus` (backend/app/services/convert/ocr.py). */
export interface OcrStatus {
  available: boolean;
  enabled: boolean;
  executable: string | null;
  version: string | null;
  languages: string[];
  requested: string;
  used: string | null;
  detail: string | null;
}
