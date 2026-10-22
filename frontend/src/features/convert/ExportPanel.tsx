import { Download } from "lucide-react";
import { useState } from "react";

import { toast } from "../../components/Toaster";
import { api } from "../../lib/api";
import { saveFile } from "../../lib/desktop";
import type { ExportFormat } from "../../types/convert";
import { Panel } from "./panels";

const FORMATS: { value: ExportFormat; label: string; detail: string }[] = [
  { value: "csv-fr", label: "CSV français", detail: "« ; », virgule décimale, JJ/MM/AAAA — s'ouvre tel quel dans Excel" },
  { value: "xlsx", label: "Excel (.xlsx)", detail: "Dates et montants typés, en-tête figé et filtrable" },
  { value: "csv", label: "CSV standard", detail: "« , », point décimal, dates ISO — pour les autres logiciels" },
  { value: "txt", label: "TXT tabulé", detail: "Colonnes séparées par des tabulations" },
  { value: "json", label: "JSON atelier-table", detail: "Table d'échange de la suite (Nexus, Viz)" },
];

/** Exports : seules les colonnes incluses, dans l'ordre affiché. */
export function ExportPanel({ conversionId }: { conversionId: string }) {
  const [busy, setBusy] = useState<ExportFormat | null>(null);

  const run = async (format: ExportFormat) => {
    setBusy(format);
    try {
      const { blob, name } = await api.conversions.export(conversionId, format);
      const outcome = await saveFile(blob, name);
      if (outcome.kind === "saved") toast(`Enregistré : ${outcome.path}`);
      else if (outcome.kind === "downloaded") toast(`« ${name} » téléchargé.`);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Panel title="Exporter" icon={Download}>
      <ul className="space-y-1.5">
        {FORMATS.map((f) => (
          <li key={f.value}>
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => void run(f.value)}
              className="flex w-full items-start gap-2 rounded-md border border-border px-2.5 py-2 text-left hover:border-border-strong hover:bg-accent-faint disabled:opacity-50"
            >
              <Download className="mt-0.5 size-3.5 shrink-0 text-accent-ink" aria-hidden />
              <span className="min-w-0">
                <span className="block text-sm font-medium">{busy === f.value ? "Préparation…" : f.label}</span>
                <span className="block text-[11px] text-muted">{f.detail}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
