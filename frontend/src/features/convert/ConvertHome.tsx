import { ArrowRight, FileSpreadsheet, FileText, Landmark, ScanText, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { toast } from "../../components/Toaster";
import { api } from "../../lib/api";
import { KIND_LABELS, formatWhen } from "../../lib/format";
import { conversionPath, navigate } from "../../lib/router";
import type { ConversionSummary, SampleInfo } from "../../types/convert";
import { Dropzone } from "./Dropzone";

const SAMPLE_ICONS: Record<string, typeof FileText> = { pdf: FileText, csv: FileSpreadsheet, ofx: Landmark };
const SCAN_ICON = ScanText;

/** Accueil : zone de dépôt, exemples, conversions récentes. */
export function ConvertHome() {
  const [busy, setBusy] = useState(false);
  const [samples, setSamples] = useState<SampleInfo[]>([]);
  const [recent, setRecent] = useState<ConversionSummary[]>([]);

  useEffect(() => {
    api.samples.list().then(setSamples, () => undefined);
    api.conversions.list().then((l) => setRecent(l.slice(0, 5)), () => undefined);
  }, []);

  const upload = async (file: File) => {
    setBusy(true);
    try {
      const conv = await api.conversions.upload(file);
      navigate(conversionPath(conv.id));
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  };

  const sample = async (name: string) => {
    setBusy(true);
    try {
      const conv = await api.samples.load(name);
      navigate(conversionPath(conv.id));
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-4 lg:p-8">
      <section>
        <h2 className="atelier-title text-xl font-semibold">Convertir un fichier pour Atelier Tab</h2>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Un relevé bancaire en PDF devient une table propre — Date, Libellé, Débit, Crédit, Montant — que vous exportez en CSV ou envoyez directement dans un projet d'Atelier Tab.
        </p>
      </section>

      <Dropzone busy={busy} onFile={(f) => void upload(f)} />

      <div className="grid gap-6 md:grid-cols-2">
        <section aria-labelledby="samples-title">
          <h3 id="samples-title" className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="size-4 text-accent-ink" aria-hidden /> Essayer avec un exemple
          </h3>
          <ul className="mt-3 space-y-2">
            {samples.map((s) => {
              const Icon = s.name.includes("scanne") ? SCAN_ICON : (SAMPLE_ICONS[s.name.split(".").pop() ?? ""] ?? FileText);
              return (
                <li key={s.name}>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void sample(s.name)}
                    className="group flex w-full items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2.5 text-left hover:border-border-strong hover:bg-accent-faint disabled:opacity-50"
                  >
                    <Icon className="size-4 shrink-0 text-accent-ink" aria-hidden />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">{s.label}</span>
                      <span className="block truncate text-xs text-muted">{s.description}</span>
                    </span>
                    <ArrowRight className="size-4 text-muted group-hover:text-fg" aria-hidden />
                  </button>
                </li>
              );
            })}
            {!samples.length && <li className="text-xs text-muted">Aucun exemple livré avec cette installation.</li>}
          </ul>
        </section>

        <section aria-labelledby="recent-title">
          <h3 id="recent-title" className="text-sm font-semibold">
            Conversions récentes
          </h3>
          <ul className="mt-3 space-y-2">
            {recent.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => navigate(conversionPath(c.id))}
                  className="flex w-full items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2.5 text-left hover:border-border-strong hover:bg-accent-faint"
                >
                  <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted">{KIND_LABELS[c.source.kind] ?? c.source.kind}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{c.name}</span>
                    <span className="block truncate text-xs text-muted">
                      {c.detected} · {formatWhen(c.updated_at)}
                    </span>
                  </span>
                </button>
              </li>
            ))}
            {!recent.length && <li className="text-xs text-muted">Vos conversions apparaîtront ici.</li>}
          </ul>
        </section>
      </div>
    </div>
  );
}
