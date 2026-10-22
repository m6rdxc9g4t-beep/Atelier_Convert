import clsx from "clsx";
import { CircleAlert, CircleCheck, X } from "lucide-react";
import { useEffect, useState } from "react";

export interface Toast {
  id: number;
  kind: "ok" | "error";
  text: string;
}

type Listener = (toasts: Toast[]) => void;
let toasts: Toast[] = [];
let next = 1;
const listeners = new Set<Listener>();

function publish() {
  listeners.forEach((l) => l(toasts));
}

/** Affiche un message éphémère (6 s ; 10 s pour une erreur). */
export function toast(text: string, kind: Toast["kind"] = "ok"): void {
  const item = { id: next++, kind, text };
  toasts = [...toasts, item].slice(-4);
  publish();
  setTimeout(() => dismiss(item.id), kind === "error" ? 10_000 : 6_000);
}

export function dismiss(id: number): void {
  toasts = toasts.filter((t) => t.id !== id);
  publish();
}

/** Zone des messages éphémères, annoncée aux lecteurs d'écran. */
export function Toaster() {
  const [items, setItems] = useState<Toast[]>(toasts);
  useEffect(() => {
    listeners.add(setItems);
    return () => {
      listeners.delete(setItems);
    };
  }, []);
  return (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} role={t.kind === "error" ? "alert" : "status"} className="atelier-pop pointer-events-auto flex items-start gap-2.5 rounded-lg border bg-surface p-3 text-sm">
          {t.kind === "ok" ? <CircleCheck className="mt-0.5 size-4 shrink-0 text-positive" aria-hidden /> : <CircleAlert className="mt-0.5 size-4 shrink-0 text-negative" aria-hidden />}
          <p className={clsx("min-w-0 flex-1 break-words", t.kind === "error" && "text-negative")}>{t.text}</p>
          <button type="button" onClick={() => dismiss(t.id)} aria-label="Fermer" className="rounded p-0.5 text-muted hover:text-fg">
            <X className="size-3.5" aria-hidden />
          </button>
        </div>
      ))}
    </div>
  );
}
