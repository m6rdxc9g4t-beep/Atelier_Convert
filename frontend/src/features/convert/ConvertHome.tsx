import { ArrowRight, FileSpreadsheet, FileText, Landmark, ScanText } from "lucide-react";
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
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-6 lg:px-8 lg:py-8">
      <section>
        <h2 className="text-xl font-semibold tracking-[-0.012em]">Convertir un fichier pour Atelier Tab</h2>
        <p className="mt-1.5 max-w-2xl text-sm text-muted">
          Un relevé bancaire en PDF devient une table propre — Date, Libellé, Débit, Crédit, Montant — que vous exportez en CSV ou envoyez directement dans un projet d'Atelier Tab.
        </p>
      </section>

      <Dropzone busy={busy} onFile={(f) => void upload(f)} />

      <div className="grid gap-x-6 gap-y-8 md:grid-cols-2">
        <section aria-labelledby="samples-title" className="min-w-0">
          <h3 id="samples-title" className="mb-2 text-sm font-semibold">
            Essayer avec un exemple
          </h3>
          {samples.length ? (
            <ul className="atelier-card divide-y divide-line overflow-hidden">
              {samples.map((s) => {
                const Icon = s.name.includes("scanne") ? SCAN_ICON : (SAMPLE_ICONS[s.name.split(".").pop() ?? ""] ?? FileText);
                return (
                  <li key={s.name}>
                    <button type="button" disabled={busy} onClick={() => void sample(s.name)} className="at-row group">
                      <Icon className="size-4 shrink-0 text-faint" aria-hidden />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{s.label}</span>
                        <span className="block truncate text-xs text-muted">{s.description}</span>
                      </span>
                      <ArrowRight className="size-4 shrink-0 text-faint transition-[color,translate] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:translate-x-[3px] group-hover:text-accent-ink" aria-hidden />
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-xs text-muted">Aucun exemple livré avec cette installation.</p>
          )}
        </section>

        <section aria-labelledby="recent-title" className="min-w-0">
          <h3 id="recent-title" className="mb-2 text-sm font-semibold">
            Conversions récentes
          </h3>
          {recent.length ? (
            <ul className="atelier-card divide-y divide-line overflow-hidden">
              {recent.map((c) => (
                <li key={c.id}>
                  <button type="button" onClick={() => navigate(conversionPath(c.id))} className="at-row">
                    <span className="at-tag w-11 shrink-0 justify-center">{KIND_LABELS[c.source.kind] ?? c.source.kind}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{c.name}</span>
                      <span className="block truncate text-xs text-muted tabular-nums">
                        {c.detected} · {formatWhen(c.updated_at)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted">Vos conversions apparaîtront ici.</p>
          )}
        </section>
      </div>
    </div>
  );
}
