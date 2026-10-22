import clsx from "clsx";
import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api } from "../../lib/api";
import type { TabStatus } from "../../types/convert";

/** Dossier de données d'Atelier Tab vu par Convert (ATELIER_TAB_DATA_DIR dans backend/.env pour le changer). */
export function TabSection() {
  const [status, setStatus] = useState<TabStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(() => {
    setLoading(true);
    api
      .tab()
      .then(setStatus, (e: unknown) => setStatus({ found: false, directory: "", projects: [], detail: e instanceof Error ? e.message : String(e) }))
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  return (
    <section className="atelier-card rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Atelier Tab</h2>
        <button type="button" onClick={load} aria-label="Revérifier le dossier d'Atelier Tab" className="rounded p-1.5 text-muted hover:bg-surface-2 hover:text-fg">
          <RefreshCw className={clsx("size-4", loading && "animate-spin")} aria-hidden />
        </button>
      </div>
      <p className="mt-1 text-xs text-muted">
        « Envoyer dans Atelier Tab » écrit une nouvelle table dans ce dossier (fichier tables/&lt;id&gt;.json) ; Tab la rattache au projet choisi et l'affiche aussitôt. Aucun autre fichier n'est modifié.
      </p>
      {status && (
        <div className="mt-3 flex items-start gap-3 text-sm">
          <span className={clsx("mt-1.5 size-2 shrink-0 rounded-full", status.found ? "bg-positive" : "bg-muted/50")} aria-hidden />
          <span className="min-w-0">
            <span className="block font-medium">{status.found ? `${status.projects.length} projet(s) disponible(s)` : "Dossier introuvable"}</span>
            <span className="block truncate font-mono text-[11px] text-muted" title={status.directory}>
              {status.directory}
            </span>
            {status.detail && <span className="block text-xs text-muted">{status.detail}</span>}
          </span>
        </div>
      )}
      <p className="mt-3 text-[11px] text-muted">Autre emplacement : ATELIER_TAB_DATA_DIR=/chemin/vers/Atelier_Tab dans backend/.env, puis relancer Atelier Convert.</p>
    </section>
  );
}
