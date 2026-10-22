import { ExternalLink, RefreshCw, Send, Table2 } from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useState } from "react";

import { toast } from "../../components/Toaster";
import { api } from "../../lib/api";
import { openExternal } from "../../lib/desktop";
import { formatWhen } from "../../lib/format";
import { suiteApps } from "../../lib/suite";
import type { ConversionView, TabStatus } from "../../types/convert";
import { Field, Panel, inputClass } from "./panels";

/**
 * « Envoyer dans Atelier Tab » : une nouvelle table dans le projet choisi. Convert écrit le fichier de la table
 * dans le dossier de données de Tab, qui l'affiche aussitôt (aucun réseau, aucun autre fichier touché).
 */
export function TabPanel({ conversion, onSent }: { conversion: ConversionView; onSent: () => void }) {
  const [status, setStatus] = useState<TabStatus | null>(null);
  const [project, setProject] = useState("");
  const [name, setName] = useState(conversion.name);
  const [busy, setBusy] = useState(false);
  const ids = { project: useId(), name: useId() };
  const tabUrl = useMemo(() => suiteApps().find((a) => a.id === "tab")?.url ?? "http://127.0.0.1:4175", []);

  const load = useCallback(() => {
    api.tab().then(
      (s) => {
        setStatus(s);
        setProject((p) => (s.projects.some((x) => x.id === p) ? p : (s.projects[0]?.id ?? "")));
      },
      (e: unknown) => setStatus({ found: false, directory: "", projects: [], detail: e instanceof Error ? e.message : String(e) }),
    );
  }, []);
  useEffect(load, [load]);
  useEffect(() => setName(conversion.name), [conversion.name]);

  const workspaces = useMemo(() => {
    const groups = new Map<string, TabStatus["projects"]>();
    for (const p of status?.projects ?? []) groups.set(p.workspace || "Sans espace", [...(groups.get(p.workspace || "Sans espace") ?? []), p]);
    return [...groups.entries()];
  }, [status]);

  const send = async () => {
    setBusy(true);
    try {
      const res = await api.conversions.sendToTab(conversion.id, project, name.trim() || null);
      toast(`Table « ${res.table_name} » créée dans « ${res.project_name} » (${res.rows} lignes, ${res.columns} colonnes).`);
      onSent();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
      load();
    } finally {
      setBusy(false);
    }
  };

  const included = conversion.table_columns.filter((c) => c.include).length;

  return (
    <Panel title="Envoyer dans Atelier Tab" icon={Table2}>
      {!status ? (
        <p className="text-xs text-muted">Lecture du dossier d'Atelier Tab…</p>
      ) : !status.found || !status.projects.length ? (
        <div className="space-y-2 text-xs">
          <p className="text-muted">{status.detail}</p>
          {status.directory && <p className="truncate font-mono text-[11px] text-muted" title={status.directory}>{status.directory}</p>}
          <button type="button" onClick={load} className="flex items-center gap-1.5 rounded-md border border-border px-2 py-1 hover:bg-surface-2">
            <RefreshCw className="size-3" aria-hidden /> Revérifier
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <Field label="Projet" htmlFor={ids.project}>
            <select id={ids.project} value={project} onChange={(e) => setProject(e.target.value)} className={inputClass}>
              {workspaces.map(([ws, projects]) => (
                <optgroup key={ws} label={ws}>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </Field>
          <Field label="Nom de la nouvelle table" htmlFor={ids.name}>
            <input id={ids.name} value={name} maxLength={200} onChange={(e) => setName(e.target.value)} className={inputClass} />
          </Field>
          <button
            type="button"
            disabled={busy || !project || !included}
            onClick={() => void send()}
            className="atelier-btn-primary flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium disabled:opacity-40"
          >
            <Send className="size-3.5" aria-hidden />
            {busy ? "Envoi…" : `Envoyer ${conversion.rows} ligne(s)`}
          </button>
          <p className="text-[11px] text-muted">
            {included} colonne(s) incluse(s), typées (dates, montants en €). Le libellé devient le titre des lignes. Tab, s'il est ouvert, affiche la table tout de suite.
          </p>
        </div>
      )}
      {conversion.sent.length > 0 && (
        <div className="mt-3 border-t border-line pt-3">
          <p className="text-[11px] font-medium text-muted">Déjà envoyée</p>
          <ul className="mt-1 space-y-1 text-xs">
            {conversion.sent
              .slice()
              .reverse()
              .map((s) => (
                <li key={s.table_id} className="truncate" title={`${s.table_id} · ${s.rows} lignes`}>
                  « {s.table_name} » → {s.project_name} <span className="text-muted">· {formatWhen(s.at)}</span>
                </li>
              ))}
          </ul>
          <button type="button" onClick={() => openExternal(tabUrl)} className="mt-2 flex items-center gap-1.5 text-xs text-accent-ink hover:underline">
            <ExternalLink className="size-3" aria-hidden /> Ouvrir Atelier Tab
          </button>
        </div>
      )}
    </Panel>
  );
}
