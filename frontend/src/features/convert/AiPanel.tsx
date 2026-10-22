import { Sparkles, TriangleAlert } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { EnginePicker, useEngine } from "../../components/ai/EnginePicker";
import { toast } from "../../components/Toaster";
import { api } from "../../lib/api";
import type { AppInfo, ConversionView } from "../../types/convert";
import { Panel, inputClass } from "./panels";

/**
 * « Structurer avec l'IA » : le texte extrait (premières lignes) part vers le moteur choisi, qui propose une table.
 * Hors ligne, seul Ollama (local) répond. La ligne bouclier dit exactement ce qui est envoyé (docs/SUITE.md §5.2).
 */
export function AiPanel({ conversion, info, onDone }: { conversion: ConversionView; info: AppInfo | null; onDone: (c: ConversionView) => void }) {
  const engine = useEngine();
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const noteId = useId();
  useEffect(() => () => abort.current?.abort(), []);

  const lines = info?.ai_max_lines ?? 200;
  const note = `Envoyé : les ${lines} premières lignes du texte extrait de « ${conversion.source.filename} »${instructions.trim() ? " et votre précision" : ""}, rien d'autre.`;
  const toClaude = engine.label === "Claude";

  const run = async () => {
    abort.current = new AbortController();
    setBusy(true);
    try {
      const res = await api.conversions.structure(conversion.id, { provider: engine.provider, instructions: instructions.trim() || null }, abort.current.signal);
      toast(`Table proposée par ${res.provider === "anthropic" ? "Claude" : "Ollama"} (${res.conversion.rows} lignes) : vérifiez-la avant de l'envoyer.`);
      onDone(res.conversion);
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Structurer avec l'IA" icon={Sparkles} defaultOpen={conversion.rows === 0 || conversion.table_columns.length === 1}>
      <p className="mb-3 text-xs text-muted">Quand la lecture automatique ne trouve pas de table, l'IA peut en proposer une à partir du texte du document.</p>
      <EnginePicker engine={engine} note={note} />
      {toClaude && (
        <p className="mt-2 flex items-start gap-1.5 text-[11px] text-warning">
          <TriangleAlert className="mt-px size-3 shrink-0" aria-hidden />
          Avec Claude, ce texte quitte la machine (abonnement Claude Code). Pour un relevé bancaire, préférez Ollama (local).
        </p>
      )}
      <textarea
        value={instructions}
        onChange={(e) => setInstructions(e.target.value)}
        maxLength={2000}
        rows={2}
        placeholder="Précision facultative : « une ligne par facture », « ignore les sous-totaux »…"
        aria-describedby={noteId}
        aria-label="Précision pour l'IA"
        className={`${inputClass} mt-3 resize-y text-xs`}
      />
      <p id={noteId} className="sr-only">
        {note}
      </p>
      <div className="mt-2 flex gap-2">
        <button type="button" disabled={busy || engine.down} onClick={() => void run()} className="atelier-btn-primary flex-1 rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-40">
          {busy ? "L'IA structure le texte…" : "Structurer avec l'IA"}
        </button>
        {busy && (
          <button type="button" onClick={() => abort.current?.abort()} className="rounded-md border border-border px-2.5 text-xs hover:bg-surface-2">
            Annuler
          </button>
        )}
      </div>
    </Panel>
  );
}
