import clsx from "clsx";
import { CircleCheck, CircleHelp, TriangleAlert } from "lucide-react";

import { formatDate, formatMoney } from "../../lib/format";
import type { StatementSummary } from "../../types/convert";

/** Synthèse d'un relevé : période, totaux, soldes et contrôle « solde initial + opérations = solde final ». */
export function StatementCard({ statement }: { statement: StatementSummary }) {
  const s = statement;
  const items: [string, string][] = [
    ["Période", s.start && s.end ? `${formatDate(s.start)} → ${formatDate(s.end)}` : "—"],
    ["Opérations", String(s.transactions)],
    ["Débits", formatMoney(s.total_debit)],
    ["Crédits", formatMoney(s.total_credit)],
  ];
  if (s.opening_balance !== null) items.push(["Solde initial", formatMoney(s.opening_balance)]);
  if (s.closing_balance !== null) items.push(["Solde final", formatMoney(s.closing_balance)]);

  return (
    <section aria-label="Synthèse du relevé" className="atelier-card rounded-xl border border-border bg-surface p-4">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 xl:grid-cols-7">
        {items.map(([label, value], i) => (
          <div key={label} className={clsx("min-w-0", i === 0 && "col-span-2 sm:col-span-1 xl:col-span-2")}>
            <dt className="text-[11px] tracking-wide text-muted uppercase">{label}</dt>
            <dd className="mt-0.5 truncate text-sm font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      <p
        className={clsx(
          "mt-3 flex items-start gap-1.5 border-t border-line pt-3 text-xs",
          s.balance_check === "ok" ? "text-positive" : s.balance_check === "mismatch" ? "text-negative" : "text-muted",
        )}
      >
        {s.balance_check === "ok" ? (
          <CircleCheck className="mt-px size-3.5 shrink-0" aria-hidden />
        ) : s.balance_check === "mismatch" ? (
          <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
        ) : (
          <CircleHelp className="mt-px size-3.5 shrink-0" aria-hidden />
        )}
        <span>
          {s.balance_check === "ok"
            ? "Contrôle des soldes : solde initial + crédits − débits = solde final. Aucune opération ne manque."
            : s.balance_check === "mismatch"
              ? `Contrôle des soldes : écart de ${formatMoney(s.balance_gap ?? 0)}. Une opération manque peut-être, ou un montant a été mal lu : vérifiez l'aperçu.`
              : "Contrôle des soldes impossible : le document ne donne pas les soldes initial et final."}
          {s.bank ? ` Banque reconnue : ${s.bank}.` : ""}
        </span>
      </p>
    </section>
  );
}
