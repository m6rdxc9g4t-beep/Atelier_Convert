/** Client HTTP typé : seul point d'accès du front au backend FastAPI. */

import type { ClaudeModel, ProviderChoice, ProvidersResponse } from "../types/ai";
import type {
  AppInfo,
  Column,
  ConversionSummary,
  ConversionView,
  ExportFormat,
  OcrStatus,
  ParseOptions,
  SampleInfo,
  SendToTabResult,
  StructureRequest,
  StructureResult,
  TabStatus,
} from "../types/convert";

/** Miroir de `Preferences` (backend/app/services/preferences.py). */
export interface Preferences {
  online_mode: boolean;
  /** Moteur choisi (« Auto · Ollama · Claude »), mémorisé. */
  ai_provider: ProviderChoice;
  claude_model: ClaudeModel;
  /** null = modèle Ollama de la configuration (`OLLAMA_MODEL`). */
  ollama_model: string | null;
}

/** Erreur renvoyée par l'API, avec le message `detail` de FastAPI. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** `detail` brut (objet structuré, ex. liste d'erreurs du modèle). */
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  // JSON par défaut ; pour un FormData, le navigateur pose lui-même l'en-tête multipart.
  const headers = typeof init?.body === "string" ? { "Content-Type": "application/json" } : undefined;
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...init, headers: { ...headers, ...init?.headers } });
  } catch {
    throw new ApiError(0, "Backend injoignable — lancez `uvicorn main:app --reload --port 8010` dans backend/.");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
    const raw = body.detail;
    const message =
      typeof raw === "string"
        ? raw
        : Array.isArray(raw) && raw.length && typeof (raw[0] as { msg?: unknown }).msg === "string"
          ? `Entrée invalide : ${(raw[0] as { msg: string }).msg}`
          : `Erreur HTTP ${response.status}`;
    throw new ApiError(response.status, message, raw);
  }
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await send(path, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Nom du fichier d'un téléchargement (`filename*` UTF-8 de préférence). */
export function fileNameFrom(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1]);
    } catch {
      /* nom mal encodé : on garde le nom simple */
    }
  }
  const plain = /filename="([^"]+)"/i.exec(disposition);
  return plain?.[1] ?? fallback;
}

export const api = {
  health: () => request<{ status: "ok"; app: string; version: string; environment: string }>("/health"),
  /** `refresh` : revérifie Claude tout de suite (sinon état gardé 60 s par le serveur). */
  providers: (refresh = false) => request<ProvidersResponse>(`/ai/providers${refresh ? "?refresh=true" : ""}`),

  conversions: {
    list: () => request<ConversionSummary[]>("/conversions"),
    get: (id: string) => request<ConversionView>(`/conversions/${id}`),
    rows: (id: string, offset = 0, limit = 500) =>
      request<{ rows: Record<string, string | number | boolean | null>[]; total: number; offset: number }>(`/conversions/${id}/rows?offset=${offset}&limit=${limit}`),
    upload: (file: File, options?: Partial<ParseOptions>) => {
      const form = new FormData();
      form.append("file", file);
      if (options) form.append("options", JSON.stringify(options));
      return request<ConversionView>("/conversions", { method: "POST", body: form });
    },
    /** Relit le fichier d'origine avec ces options. */
    reparse: (id: string, options: ParseOptions) => request<ConversionView>(`/conversions/${id}/options`, { method: "PUT", body: JSON.stringify(options) }),
    setColumns: (id: string, columns: Column[]) => request<ConversionView>(`/conversions/${id}/columns`, { method: "PUT", body: JSON.stringify({ columns }) }),
    rename: (id: string, name: string) => request<ConversionView>(`/conversions/${id}/name`, { method: "PUT", body: JSON.stringify({ name }) }),
    remove: (id: string) => request<{ deleted: boolean }>(`/conversions/${id}`, { method: "DELETE" }),
    /** Fichier exporté (colonnes incluses), avec son nom. */
    export: async (id: string, format: ExportFormat): Promise<{ blob: Blob; name: string }> => {
      const response = await send(`/conversions/${id}/export?format=${format}`);
      return { blob: await response.blob(), name: fileNameFrom(response.headers.get("Content-Disposition"), `conversion.${format === "csv-fr" ? "csv" : format}`) };
    },
    sendToTab: (id: string, projectId: string, tableName: string | null) =>
      request<SendToTabResult>(`/conversions/${id}/send-to-tab`, { method: "POST", body: JSON.stringify({ project_id: projectId, table_name: tableName }) }),
    structure: (id: string, body: StructureRequest, signal?: AbortSignal) =>
      request<StructureResult>(`/conversions/${id}/structure`, { method: "POST", body: JSON.stringify(body), signal }),
  },

  tab: () => request<TabStatus>("/tab"),
  /** Reconnaissance de texte (Tesseract) : `refresh` revérifie tout de suite. */
  ocr: (refresh = false) => request<OcrStatus>(`/ocr${refresh ? "?refresh=true" : ""}`),

  samples: {
    list: () => request<SampleInfo[]>("/samples"),
    load: (name: string) => request<ConversionView>(`/samples/${encodeURIComponent(name)}`, { method: "POST" }),
  },

  settings: {
    get: () => request<Preferences>("/settings"),
    /** Seuls les champs envoyés changent (les autres préférences sont gardées par le serveur). */
    set: (value: Partial<Preferences>) => request<Preferences>("/settings", { method: "PUT", body: JSON.stringify(value) }),
    info: () => request<AppInfo>("/settings/info"),
  },
};
