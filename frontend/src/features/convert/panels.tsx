import clsx from "clsx";
import { ChevronDown, type LucideIcon } from "lucide-react";
import { type ReactNode, useId, useState } from "react";

/** Panneau latéral repliable (carte néon de la charte). */
export function Panel({ title, icon: Icon, children, defaultOpen = true }: { title: string; icon: LucideIcon; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <section className="atelier-card rounded-xl border border-border bg-surface">
      <h3>
        <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-semibold">
          <Icon className="size-4 text-accent-ink" aria-hidden />
          <span className="flex-1">{title}</span>
          <ChevronDown className={clsx("size-4 text-muted transition-transform", open && "rotate-180")} aria-hidden />
        </button>
      </h3>
      {open && (
        <div id={id} className="border-t border-line px-4 pt-3 pb-4">
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
      <label htmlFor={htmlFor} className="block text-xs font-medium text-muted">
        {label}
      </label>
      {children}
      {hint && <p className="text-[11px] text-muted">{hint}</p>}
    </div>
  );
}

/** Choix segmenté (radios) dans le style du sélecteur de moteur. */
export function Segmented<T extends string>({ label, value, options, onChange, disabled }: { label: string; value: T; options: { value: T; label: string; title?: string }[]; onChange: (v: T) => void; disabled?: boolean }) {
  return (
    <div className="grid gap-1 rounded-md border border-border p-0.5 text-[11px]" style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }} role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          disabled={disabled}
          title={o.title}
          onClick={() => onChange(o.value)}
          className={clsx("truncate rounded px-1 py-1.5 disabled:opacity-50", value === o.value ? "bg-accent-soft font-medium text-accent-ink" : "text-muted hover:text-fg")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const inputClass = "w-full rounded-md border border-border bg-field px-2 py-1.5 text-sm text-fg disabled:opacity-50";
