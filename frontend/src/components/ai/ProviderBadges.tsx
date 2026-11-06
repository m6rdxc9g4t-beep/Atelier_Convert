import clsx from "clsx";
import { RefreshCw } from "lucide-react";

import type { ProviderName, ProviderStatus } from "../../types/ai";

const LABELS: Record<ProviderName, string> = { ollama: "Ollama", anthropic: "Claude" };

interface ProviderBadgesProps {
  providers: ProviderStatus[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

/** État des fournisseurs IA (pastille pleine = prêt, cercle vide = indisponible, détail au survol). */
export function ProviderBadges({ providers, loading, error, onRefresh }: ProviderBadgesProps) {
  return (
    <div className="flex items-center gap-1">
      {error ? (
        <span className="px-1 text-xs font-medium text-danger" title={error}>
          API hors ligne
        </span>
      ) : (
        providers.map((p) => (
          <span
            key={p.name}
            title={p.detail ?? `${LABELS[p.name]} prêt — ${p.model}`}
            className={clsx("flex h-[26px] items-center gap-1.5 px-1.5 text-xs font-medium", p.available ? "text-fg-2" : "text-muted")}
          >
            <span aria-hidden className={clsx("size-2 rounded-full", p.available ? "bg-up" : "ring-[1.5px] ring-faint ring-inset")} />
            {LABELS[p.name]}
            <span className="sr-only">{p.available ? "disponible" : "indisponible"}</span>
          </span>
        ))
      )}
      <button
        type="button"
        onClick={onRefresh}
        aria-label="Revérifier les fournisseurs IA"
        title="Revérifier les fournisseurs IA"
        className="at-btn at-btn--ghost at-btn--sm at-btn--icon"
      >
        <RefreshCw className={clsx("size-3.5", loading && "animate-spin")} aria-hidden />
      </button>
    </div>
  );
}
