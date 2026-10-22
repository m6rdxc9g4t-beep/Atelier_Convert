import { Download, FolderOpen, Table2, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { toast } from "../../components/Toaster";
import { api } from "../../lib/api";
import { saveFile } from "../../lib/desktop";
import { KIND_LABELS, formatWhen } from "../../lib/format";
import { conversionPath, navigate } from "../../lib/router";
import type { ConversionSummary } from "../../types/convert";

/** Historique des conversions : rouvrir, exporter en CSV, supprimer. */
export function HistoryView() {
  const [items, setItems] = useState<ConversionSummary[] | null>(null);
  const [query, setQuery] = useState("");

  const load = useCallback(() => {
    api.conversions.list().then(setItems, (e: unknown) => {
      setItems([]);
      toast(e instanceof Error ? e.message : String(e), "error");
    });
  }, []);
  useEffect(load, [load]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (items ?? []).filter((c) => !q || `${c.name} ${c.source.filename} ${c.detected}`.toLowerCase().includes(q));
  }, [items, query]);

  const remove = async (c: ConversionSummary) => {
    if (!window.confirm(`Supprimer « ${c.name} » et son fichier source de l'historique ?\nLes tables déjà envoyées dans Atelier Tab restent.`)) return;
    try {
      await api.conversions.remove(c.id);
      toast(`« ${c.name} » supprimée.`);
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  };

  const exportCsv = async (c: ConversionSummary) => {
    try {
      const { blob, name } = await api.conversions.export(c.id, "csv-fr");
      const out = await saveFile(blob, name);
      if (out.kind !== "cancelled") toast(out.kind === "saved" ? `Enregistré : ${out.path}` : `« ${name} » téléchargé.`);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 lg:p-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="atelier-title text-xl font-semibold">Historique</h2>
          <p className="mt-1 text-sm text-muted">Chaque conversion garde son fichier d'origine : vous pouvez la rouvrir, la relire avec d'autres options ou la renvoyer.</p>
        </div>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rechercher…"
          aria-label="Rechercher dans l'historique"
          className="w-56 rounded-md border border-border bg-field px-2.5 py-1.5 text-sm"
        />
      </div>

      {items === null ? (
        <p className="text-sm text-muted">Chargement…</p>
      ) : !shown.length ? (
        <div className="atelier-card rounded-xl border border-border bg-surface p-8 text-center text-sm text-muted">
          {items.length ? "Aucune conversion ne correspond." : "Aucune conversion pour l'instant."}
          <div className="mt-4">
            <button type="button" onClick={() => navigate("/")} className="atelier-btn-primary rounded-md px-3 py-1.5 text-sm font-medium">
              Convertir un fichier
            </button>
          </div>
        </div>
      ) : (
        <ul className="atelier-card divide-y divide-line overflow-hidden rounded-xl border border-border bg-surface">
          {shown.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-3 hover:bg-accent-faint">
              <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted">{KIND_LABELS[c.source.kind] ?? c.source.kind}</span>
              <button type="button" onClick={() => navigate(conversionPath(c.id))} className="min-w-0 flex-1 text-left">
                <span className="block truncate text-sm font-medium">{c.name}</span>
                <span className="block truncate text-xs text-muted">
                  {c.detected} · {c.columns} colonne(s) · {formatWhen(c.updated_at)}
                </span>
              </button>
              {c.sent.length > 0 && (
                <span className="flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] text-accent-ink" title={c.sent.map((s) => `« ${s.table_name} » → ${s.project_name}`).join("\n")}>
                  <Table2 className="size-3" aria-hidden /> Envoyée dans Tab{c.sent.length > 1 ? ` ×${c.sent.length}` : ""}
                </span>
              )}
              <div className="flex items-center gap-1">
                <IconButton label={`Ouvrir ${c.name}`} onClick={() => navigate(conversionPath(c.id))} icon={FolderOpen} />
                <IconButton label={`Exporter ${c.name} en CSV`} onClick={() => void exportCsv(c)} icon={Download} />
                <IconButton label={`Supprimer ${c.name}`} onClick={() => void remove(c)} icon={Trash2} danger />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function IconButton({ label, onClick, icon: Icon, danger = false }: { label: string; onClick: () => void; icon: typeof Trash2; danger?: boolean }) {
  return (
    <button type="button" onClick={onClick} aria-label={label} title={label} className={`rounded-md p-1.5 text-muted hover:bg-surface-2 ${danger ? "hover:text-negative" : "hover:text-fg"}`}>
      <Icon className="size-4" aria-hidden />
    </button>
  );
}
