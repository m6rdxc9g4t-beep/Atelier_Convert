import clsx from "clsx";
import { ChevronDown, type LucideIcon } from "lucide-react";
import { type ReactNode, useId, useState } from "react";

/** Panneau latéral repliable (carte plate de la charte). */
export function Panel({ title, icon: Icon, children, defaultOpen = true }: { title: string; icon: LucideIcon; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <section className="atelier-card">
      <h3>
        <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)} className="flex h-10 w-full items-center gap-2 rounded-lg px-3 text-left text-sm font-semibold hover:bg-surface-2 focus-visible:outline-offset-[-2px]">
          <Icon className="size-4 text-faint" aria-hidden />
          <span className="flex-1">{title}</span>
          <ChevronDown className={clsx("size-4 text-faint transition-transform duration-200", open && "rotate-180")} aria-hidden />
        </button>
      </h3>
      {open && (
        <div id={id} className="border-t border-line px-3 pt-3 pb-3">
          {children}
        </div>
      )}
    </section>
  );
}

/** Ligne « libellé + contrôle » d'un formulaire de panneau. */
export function Field({ label, htmlFor, children, hint }: { label: string; htmlFor?: string; children: ReactNode; hint?: string }) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="block text-xs font-medium text-fg-2">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
  );
}

/** Choix segmenté (radios) : rail neutre, option choisie en surface. */
export function Segmented<T extends string>({ label, value, options, onChange, disabled }: { label: string; value: T; options: { value: T; label: string; title?: string }[]; onChange: (v: T) => void; disabled?: boolean }) {
  return (
    <div className="at-seg grid w-full" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          disabled={disabled}
          title={o.title}
          onClick={() => onChange(o.value)}
          className="truncate !px-1"
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const inputClass = "at-input";
