import clsx from "clsx";
import { Cloud, HardDrive } from "lucide-react";

import { usePreferences } from "../../hooks/usePreferences";
import type { ProviderStatus } from "../../types/ai";
import { ProviderBadges } from "../ai/ProviderBadges";
import { SuiteSwitcher } from "./SuiteSwitcher";

interface TopbarProps {
  title: string;
  providers: ProviderStatus[];
  providersLoading: boolean;
  providersError: string | null;
  onRefreshProviders: () => void;
}

/** Barre haute (44 px) : sélecteur de la suite, titre de la vue, interrupteur Hors ligne / En ligne, état des moteurs d'IA. */
export function Topbar(props: TopbarProps) {
  const { title } = props;
  const { prefs, setOnline } = usePreferences();
  const online = prefs?.online_mode ?? false;

  return (
    <header className="flex h-11 shrink-0 items-center justify-between gap-3 border-b border-line bg-bg px-3 lg:px-5">
      <div className="flex min-w-0 items-center gap-1.5">
        <SuiteSwitcher />
        <h1 className="min-w-0 truncate text-sm font-semibold">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        <div className="hidden md:block">
          <ProviderBadges providers={props.providers} loading={props.providersLoading} error={props.providersError} onRefresh={props.onRefreshProviders} />
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={online}
          onClick={() => {
            void setOnline(!online).then(props.onRefreshProviders);
          }}
          title={online ? "En ligne : Claude peut structurer un texte que vous lui envoyez. Cliquer pour repasser en local." : "Hors ligne : tout reste sur la machine. Cliquer pour activer Claude."}
          className={clsx("at-btn at-btn--sm", online && "border-transparent !bg-accent-soft text-accent-ink")}
        >
          {online ? <Cloud className="size-3.5" aria-hidden /> : <HardDrive className="size-3.5 text-muted" aria-hidden />}
          {online ? "En ligne" : "Hors ligne"}
        </button>
      </div>
    </header>
  );
}
