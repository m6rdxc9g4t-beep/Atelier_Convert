import clsx from "clsx";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";

import { TYPE_LABELS, formatCell, unconverted } from "../../lib/format";
import type { CellValue, Column, ColumnType } from "../../types/convert";

const TYPES = Object.keys(TYPE_LABELS) as ColumnType[];
/** Libellés courts du choix de type (en-têtes étroits). */
const SHORT: Record<ColumnType, string> = { text: "Texte", number: "Nombre", currency: "€", date: "Date", boolean: "Oui/non" };

/** Largeur des colonnes (px) : étroites pour les dates et montants, le texte se partage le reste (200 px au moins). */
const WIDTHS: Record<ColumnType, number | null> = { date: 118, currency: 120, number: 110, boolean: 104, text: null };
const TEXT_MIN = 200;
const INDEX_WIDTH = 44;

interface Props {
  columns: Column[];
  rows: Record<string, CellValue>[];
  total: number;
  busy: boolean;
  onColumns: (columns: Column[]) => void;
  onMore: (() => void) | null;
}

/**
 * Aperçu de la table : en-têtes modifiables (inclure, renommer, type, déplacer), cellules mises en forme.
 * Une valeur qui n'a pas pu être convertie dans le type de sa colonne est surlignée (gardée telle quelle).
 */
export function PreviewTable({ columns, rows, total, busy, onColumns, onMore }: Props) {
  const update = (index: number, patch: Partial<Column>) => onColumns(columns.map((c, i) => (i === index ? { ...c, ...patch } : c)));
  const move = (index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= columns.length) return;
    const next = [...columns];
    const [col] = next.splice(index, 1);
    if (col) next.splice(target, 0, col);
    onColumns(next);
  };
  const minWidth = INDEX_WIDTH + columns.reduce((sum, c) => sum + (WIDTHS[c.type] ?? TEXT_MIN), 0);
  const problems = rows.reduce((n, r) => n + columns.filter((c) => c.include && unconverted(r[c.key] ?? null, c.type)).length, 0);

  return (
    <section aria-label="Aperçu de la table" className="atelier-card flex min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-surface">
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="convert-table table-fixed border-collapse text-sm" style={{ width: `max(100%, ${minWidth}px)` }}>
          <colgroup>
            <col style={{ width: INDEX_WIDTH }} />
            {columns.map((c) => (
              <col key={c.key} style={WIDTHS[c.type] ? { width: WIDTHS[c.type] ?? undefined } : undefined} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th scope="col" className="border-b border-line px-2 py-2 text-right text-[11px] font-normal text-muted">
                #
              </th>
              {columns.map((col, i) => (
                <th key={col.key} scope="col" className={clsx("border-b border-l border-line px-2 py-1.5 text-left align-top font-normal", !col.include && "opacity-50")}>
                  <HeaderCell
                    column={col}
                    disabled={busy}
                    first={i === 0}
                    last={i === columns.length - 1}
                    onChange={(patch) => update(i, patch)}
                    onMove={(d) => move(i, d)}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, r) => (
              <tr key={r} className="hover:bg-accent-faint">
                <td className="border-b border-line px-2 py-1.5 text-right text-[11px] text-muted tabular-nums">{r + 1}</td>
                {columns.map((col) => {
                  const value = row[col.key] ?? null;
                  const bad = unconverted(value, col.type);
                  return (
                    <td
                      key={col.key}
                      title={bad ? `Valeur gardée telle quelle : ce n'est pas un ${TYPE_LABELS[col.type].toLowerCase()}` : undefined}
                      className={clsx(
                        "truncate border-b border-l border-line px-2 py-1.5",
                        (col.type === "number" || col.type === "currency") && "num",
                        col.type === "currency" && typeof value === "number" && value < 0 && "text-negative",
                        !col.include && "text-muted opacity-50",
                        bad && "bg-warning/15 text-warning",
                      )}
                    >
                      {formatCell(value, col.type)}
                    </td>
                  );
                })}
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={columns.length + 1} className="px-4 py-10 text-center text-sm text-muted">
                  Aucune ligne. Essayez d'autres options de lecture, ou « Structurer avec l'IA ».
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-3 py-2 text-xs text-muted">
        <span>
          {rows.length.toLocaleString("fr-FR")} ligne(s) affichée(s) sur {total.toLocaleString("fr-FR")} · {columns.filter((c) => c.include).length} colonne(s) incluse(s)
          {problems > 0 && <span className="text-warning"> · {problems} valeur(s) non converties (surlignées)</span>}
        </span>
        {onMore && (
          <button type="button" onClick={onMore} className="rounded-md border border-border px-2 py-1 hover:bg-surface-2 hover:text-fg">
            Afficher plus de lignes
          </button>
        )}
      </footer>
    </section>
  );
}

function HeaderCell({
  column,
  disabled,
  first,
  last,
  onChange,
  onMove,
}: {
  column: Column;
  disabled: boolean;
  first: boolean;
  last: boolean;
  onChange: (patch: Partial<Column>) => void;
  onMove: (delta: number) => void;
}) {
  const [label, setLabel] = useState(column.label);
  useEffect(() => setLabel(column.label), [column.label]);
  const commit = () => {
    const trimmed = label.trim();
    if (!trimmed) setLabel(column.label);
    else if (trimmed !== column.label) onChange({ label: trimmed });
  };
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <input
          type="checkbox"
          checked={column.include}
          disabled={disabled}
          onChange={(e) => onChange({ include: e.target.checked })}
          aria-label={`Inclure la colonne ${column.label}`}
          title={column.include ? "Colonne exportée — décocher pour l'écarter" : "Colonne écartée — cocher pour l'exporter"}
        />
        <input
          value={label}
          disabled={disabled}
          onChange={(e) => setLabel(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
            if (e.key === "Escape") setLabel(column.label);
          }}
          aria-label={`Nom de la colonne ${column.label}`}
          className="min-w-0 flex-1 rounded border border-transparent bg-transparent px-1 py-0.5 font-semibold text-fg hover:border-border"
        />
      </div>
      <div className="flex items-center gap-0.5">
        <select
          value={column.type}
          disabled={disabled}
          onChange={(e) => onChange({ type: e.target.value as ColumnType })}
          aria-label={`Type de la colonne ${column.label}`}
          title={TYPE_LABELS[column.type]}
          className="min-w-0 flex-1 rounded border border-border bg-field px-1 py-0.5 text-[11px] text-muted"
        >
          {TYPES.map((t) => (
            <option key={t} value={t} title={TYPE_LABELS[t]}>
              {SHORT[t]}
            </option>
          ))}
        </select>
        <button type="button" disabled={disabled || first} onClick={() => onMove(-1)} aria-label={`Déplacer ${column.label} à gauche`} className="rounded text-muted hover:text-fg disabled:opacity-30">
          <ChevronLeft className="size-3.5" aria-hidden />
        </button>
        <button type="button" disabled={disabled || last} onClick={() => onMove(1)} aria-label={`Déplacer ${column.label} à droite`} className="rounded text-muted hover:text-fg disabled:opacity-30">
          <ChevronRight className="size-3.5" aria-hidden />
        </button>
      </div>
    </div>
  );
}
