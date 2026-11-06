import clsx from "clsx";
import { FileInput, History, type LucideIcon, Settings } from "lucide-react";

import type { Route } from "../../lib/router";
import { navigate } from "../../lib/router";
import { AtelierBrand } from "./AtelierBrand";
import { ThemeSwitch } from "./ThemeSwitch";

interface NavItem {
  label: string;
  icon: LucideIcon;
  path: string;
  match: Route["name"][];
}

const NAV: NavItem[] = [
  { label: "Convertir", icon: FileInput, path: "/", match: ["convert"] },
  { label: "Historique", icon: History, path: "/historique", match: ["history"] },
  { label: "Réglages", icon: Settings, path: "/reglages", match: ["settings"] },
];

/**
 * Barre latérale de la suite (232 px) : marque, navigation, puis en pied la note « local » et le thème.
 * Sous 1024 px : rail d'icônes.
 */
export function Sidebar({ route }: { route: Route }) {
  return (
    <aside className="flex w-[52px] shrink-0 flex-col border-r border-line bg-sidebar px-2 pt-2 pb-2 lg:w-[232px] lg:pt-3">
      <div className="mb-3 flex h-8 items-center justify-center lg:justify-start lg:px-1">
        <AtelierBrand nameClassName="hidden lg:inline" />
      </div>
      <nav className="flex flex-col gap-px" aria-label="Navigation principale">
        {NAV.map(({ label, icon: Icon, path, match }) => {
          const current = match.includes(route.name);
          return (
            <button
              key={label}
              type="button"
              title={label}
              onClick={() => navigate(path)}
              aria-current={current ? "page" : undefined}
              className={clsx(
                "flex h-[30px] items-center justify-center gap-2.5 rounded-md px-2 text-sm font-medium transition-colors lg:justify-start",
                current ? "atelier-nav-active [&>svg]:text-fg" : "text-fg-2 hover:bg-surface-2 hover:text-fg [&>svg]:text-faint",
              )}
            >
              <Icon className="size-4 shrink-0" aria-hidden />
              <span className="hidden lg:inline">{label}</span>
            </button>
          );
        })}
      </nav>
      <div className="mt-auto flex flex-col items-center gap-3 lg:items-start">
        <p className="hidden px-2 text-xs leading-snug text-muted lg:block">Tout est converti sur cette machine. Les tables envoyées apparaissent dans Atelier Tab.</p>
        <ThemeSwitch vertical className="lg:grid-flow-col" />
      </div>
    </aside>
  );
}
