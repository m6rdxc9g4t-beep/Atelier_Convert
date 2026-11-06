import clsx from "clsx";
import { Monitor, Moon, Sun } from "lucide-react";

import { type ThemePreference, useTheme } from "../../hooks/useTheme";

const OPTIONS: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: "system", label: "Système", icon: Monitor },
  { value: "light", label: "Clair", icon: Sun },
  { value: "dark", label: "Sombre", icon: Moon },
];

/**
 * Choix du thème (Système / Clair / Sombre), comme au pied de la barre latérale du portail.
 * Préférence commune à la suite : `window.atelierTheme.set` (voir useTheme).
 */
export function ThemeSwitch({ vertical = false, className }: { vertical?: boolean; className?: string }) {
  const { preference, setPreference } = useTheme();
  return (
    <div role="group" aria-label="Thème" className={clsx("at-seg", vertical && "grid-flow-row", className)}>
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button key={value} type="button" aria-pressed={preference === value} title={`Thème : ${label.toLowerCase()}`} onClick={() => setPreference(value)} className="!px-[7px]">
          <Icon className="size-3.5" aria-hidden />
          <span className="sr-only">{label}</span>
        </button>
      ))}
    </div>
  );
}
