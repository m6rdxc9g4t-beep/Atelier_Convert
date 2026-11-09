import { ArrowRight, ExternalLink, FileSpreadsheet, FileText } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { toast } from "../../components/Toaster";
import { api } from "../../lib/api";
import { openExternal } from "../../lib/desktop";
import { APP_LABELS, THIS_APP, pickHistoire, readRemembered, remember, stepsAround } from "../../lib/exemples";
import { conversionPath, navigate } from "../../lib/router";
import { suiteApps } from "../../lib/suite";
import type { ExempleHistoire } from "../../types/convert";

/**
 * « Exemples de la suite » : une histoire fictive suivie d'une app à l'autre. Ici, on convertit ses relevés et ses
 * exports ; le parcours dit quoi faire ensuite (Tab, Viz, Trésorerie…), avec les mêmes données.
 */
export function SuiteExamples({ busy, setBusy }: { busy: boolean; setBusy: (b: boolean) => void }) {
  const [histoires, setHistoires] = useState<ExempleHistoire[]>([]);
  const [selected, setSelected] = useState<string | null>(readRemembered());

  useEffect(() => {
    api.exemples.list().then(setHistoires, () => undefined);
  }, []);

  const histoire = pickHistoire(histoires, selected);
  const steps = histoire ? stepsAround(histoire) : null;
  const nextUrl = useMemo(
    () => (steps?.next ? suiteApps().find((a) => a.id === steps.next?.app)?.url : undefined),
    [steps?.next],
  );

  if (!histoire || !steps) return null;

  const choose = (id: string) => {
    setSelected(id);
    remember(id);
  };

  const convert = async (index: number) => {
    setBusy(true);
    try {
      const conv = await api.exemples.convert(histoire.id, index);
      navigate(conversionPath(conv.id));
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="suite-examples-title" className="min-w-0 space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h3 id="suite-examples-title" className="text-sm font-semibold">
            Exemples de la suite
          </h3>
          <p className="mt-0.5 text-xs text-muted">
            Des histoires fictives qui traversent toute la suite : ce que vous convertissez ici, Tab le range, Viz l'analyse,
            Trésorerie le compare au budget.
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs text-muted">
          <span className="sr-only sm:not-sr-only">Histoire</span>
          <select
            className="at-input w-64 max-w-full"
            value={histoire.id}
            onChange={(e) => choose(e.target.value)}
            aria-label="Histoire d'exemple"
          >
            {histoires.map((h) => (
              <option key={h.id} value={h.id}>
                {h.secteur} · {h.titre}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="atelier-card overflow-hidden">
        <div className="space-y-3 p-4">
          <div>
            <p className="text-sm font-medium">
              {histoire.titre} <span className="font-normal text-muted">— {histoire.sous_titre}</span>
            </p>
            <p className="mt-1 max-w-3xl text-xs text-muted">{histoire.resume}</p>
          </div>
          <ol className="flex flex-wrap gap-1.5" aria-label="Parcours de l'histoire dans la suite">
            {histoire.parcours.map((e, i) => (
              <li
                key={e.app}
                aria-current={e.app === THIS_APP ? "step" : undefined}
                title={e.texte}
                className={`at-tag gap-1.5 ${e.app === THIS_APP ? "bg-accent-soft text-accent-ink" : ""}`}
              >
                <span className="tabular-nums text-faint">{i + 1}</span>
                {APP_LABELS[e.app]}
              </li>
            ))}
          </ol>
          {steps.current ? <p className="text-xs">{steps.current.texte}</p> : null}
        </div>

        <ul className="divide-y divide-line border-t border-line">
          {histoire.fichiers.map((f) => {
            const Icon = f.type === "releve" ? FileText : FileSpreadsheet;
            return (
              <li key={f.index}>
                <button type="button" disabled={busy} onClick={() => void convert(f.index)} className="at-row group">
                  <Icon className="size-4 shrink-0 text-faint" aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{f.titre}</span>
                    <span className="block truncate text-xs text-muted">{f.description}</span>
                  </span>
                  <ArrowRight
                    className="size-4 shrink-0 text-faint transition-[color,translate] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:translate-x-[3px] group-hover:text-accent-ink"
                    aria-hidden
                  />
                </button>
              </li>
            );
          })}
        </ul>

        {steps.next ? (
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-3 text-xs">
            <p className="min-w-0 text-muted">
              <span className="font-medium text-fg">Ensuite, {APP_LABELS[steps.next.app]}</span> — {steps.next.texte}
            </p>
            {nextUrl ? (
              <button type="button" className="at-btn at-btn--sm at-btn--ghost" onClick={() => openExternal(nextUrl)}>
                Ouvrir Atelier {APP_LABELS[steps.next.app]}
                <ExternalLink className="size-3.5" aria-hidden />
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
