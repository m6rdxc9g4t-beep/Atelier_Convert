import clsx from "clsx";
import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api } from "../../lib/api";
import type { OcrStatus } from "../../types/convert";

const INSTALL: { os: string; command: string }[] = [
  { os: "macOS", command: "brew install tesseract tesseract-lang" },
  { os: "Windows", command: "winget install UB-Mannheim.TesseractOCR" },
  { os: "Linux", command: "sudo apt install tesseract-ocr tesseract-ocr-fra" },
];

/** Reconnaissance de texte (OCR) : Tesseract sur la machine, pour les PDF scannés et les photos de relevés. */
export function OcrSection() {
  const [status, setStatus] = useState<OcrStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback((refresh = false) => {
    setLoading(true);
    api
      .ocr(refresh)
      .then(setStatus, (e: unknown) =>
        setStatus({ available: false, enabled: true, executable: null, version: null, languages: [], requested: "fra+eng", used: null, detail: e instanceof Error ? e.message : String(e) }),
      )
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => load(), [load]);

  const french = status?.used?.split("+").includes("fra") ?? false;

  return (
    <section className="atelier-card rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Reconnaissance de texte (OCR)</h2>
        <button type="button" onClick={() => load(true)} aria-label="Revérifier l'OCR" className="rounded p-1.5 text-muted hover:bg-surface-2 hover:text-fg">
          <RefreshCw className={clsx("size-4", loading && "animate-spin")} aria-hidden />
        </button>
      </div>
      <p className="mt-1 text-xs text-muted">
        Un relevé scanné (PDF sans texte) ou une photo est lu par Tesseract, sur cette machine : rien n'est envoyé. Les montants et les dates restent à vérifier ; le contrôle des
        soldes signale une opération mal lue.
      </p>
      {status && (
        <div className="mt-3 flex items-start gap-3 text-sm">
          <span className={clsx("mt-1.5 size-2 shrink-0 rounded-full", status.available ? (french ? "bg-positive" : "bg-warning") : "bg-muted/50")} aria-hidden />
          <span className="min-w-0">
            <span className="block font-medium">
              {status.available ? `Tesseract ${status.version ?? ""} — langues : ${status.used}` : status.enabled ? "OCR indisponible" : "OCR désactivé"}
            </span>
            {status.executable && (
              <span className="block truncate font-mono text-[11px] text-muted" title={status.executable}>
                {status.executable}
              </span>
            )}
            {status.detail && <span className="block text-xs text-muted">{status.detail}</span>}
          </span>
        </div>
      )}
      {status && (!status.available || !french) && status.enabled && (
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-lg border border-border bg-surface-2 p-3 text-xs">
          {INSTALL.map((i) => (
            <div key={i.os} className="contents">
              <dt className="text-muted">{i.os}</dt>
              <dd className="font-mono select-all">{i.command}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className="mt-3 text-[11px] text-muted">
        Réglages (backend/.env) : CONVERT_OCR_TESSERACT (chemin de l'exécutable), CONVERT_OCR_LANGUAGES (« fra+eng »), CONVERT_OCR_TESSDATA (dossier des langues), CONVERT_OCR_ENABLED.
      </p>
    </section>
  );
}
