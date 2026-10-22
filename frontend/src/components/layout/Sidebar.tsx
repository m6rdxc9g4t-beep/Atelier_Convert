import clsx from "clsx";
import { FileInput, History, type LucideIcon, Settings } from "lucide-react";

import type { Route } from "../../lib/router";
import { navigate } from "../../lib/router";
import { AtelierBrand } from "./AtelierBrand";

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

/** Navigation principale ; icônes seules sous 1024px. */
export function Sidebar({ route }: { route: Route }) {
  return (
    <aside className="flex w-12 shrink-0 flex-col border-r border-border bg-sidebar lg:w-52">
      <div className="flex h-12 items-center border-b border-border px-2 lg:px-3">
        <AtelierBrand nameClassName="hidden lg:inline" />
      </div>
      <nav className="flex flex-col gap-1 p-1.5" aria-label="Navigation principale">
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
                "flex h-9 items-center gap-3 rounded-md px-2.5 text-sm transition-colors outline-none focus-visible:ring-2 focus-visible:ring-focus",
                current ? "atelier-nav-active font-medium [&>svg]:text-accent-ink" : "text-muted hover:bg-accent-faint hover:text-fg",
              )}
            >
              <Icon className="size-4 shrink-0" aria-hidden />
              <span className="hidden lg:inline">{label}</span>
            </button>
          );
        })}
      </nav>
      <p className="mt-auto hidden p-3 text-[11px] leading-snug text-muted lg:block">
        Tout est converti sur cette machine. Les tables envoyées apparaissent dans Atelier Tab.
      </p>
    </aside>
  );
}
