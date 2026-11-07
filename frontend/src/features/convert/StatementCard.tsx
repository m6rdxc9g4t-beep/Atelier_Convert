import clsx from "clsx";
import { CircleCheck, CircleHelp, TriangleAlert } from "lucide-react";

import { formatDate, formatMoney } from "../../lib/format";
import type { StatementSummary } from "../../types/convert";

/**
 * Synthèse d'un relevé : rangée de cartes de chiffres (`atelier-kpi`, coins de 12 px) — opérations et période,
 * débits, crédits, soldes — puis le contrôle « solde initial + opérations = solde final ».
 */
export function StatementCard({ statement }: { statement: StatementSummary }) {
  const s = statement;
  const period = s.start && s.end ? `${formatDate(s.start)} → ${formatDate(s.end)}` : null;
  const items: { label: string; value: string; note?: string }[] = [
    { label: "Opérations", value: String(s.transactions), note: period ?? "Période inconnue" },
    { label: "Débits", value: formatMoney(s.total_debit) },
    { label: "Crédits", value: formatMoney(s.total_credit) },
  ];
  if (s.opening_balance !== null) items.push({ label: "Solde initial", value: formatMoney(s.opening_balance) });
  if (s.closing_balance !== null) items.push({ label: "Solde final", value: formatMoney(s.closing_balance) });

  return (
    <section aria-label="Synthèse du relevé" className="space-y-2">
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 lg:grid-cols-5">
        {items.map(({ label, value, note }, i) => (
          <div key={label} className={clsx("atelier-kpi", i === 0 && "col-span-2 sm:col-span-1")}>
            <dt className="atelier-kpi__label">{label}</dt>
            <dd className="atelier-kpi__value truncate" title={value}>
              {value}
            </dd>
            {note && (
              <dd className="atelier-kpi__note truncate">
                <span className="sr-only">Période : </span>
                {note}
              </dd>
            )}
          </div>
        ))}
      </dl>
      <p
        className={clsx(
          "flex items-start gap-1.5 px-1 text-xs",
          s.balance_check === "mismatch" ? "font-medium text-danger" : "text-muted",
        )}
      >
        {s.balance_check === "ok" ? (
          <CircleCheck className="mt-px size-3.5 shrink-0 text-up" aria-hidden />
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
