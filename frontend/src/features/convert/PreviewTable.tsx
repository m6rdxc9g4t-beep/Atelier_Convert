import clsx from "clsx";
import { ArrowLeftRight, ChevronLeft, ChevronRight } from "lucide-react";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import { TYPE_LABELS, editText, formatCell, unconverted } from "../../lib/format";
import { type CellEdit, type CellValue, type Column, type ColumnType, cellRef } from "../../types/convert";

const TYPES = Object.keys(TYPE_LABELS) as ColumnType[];
/** Libellés courts du choix de type (en-têtes étroits). */
const SHORT: Record<ColumnType, string> = { text: "Texte", number: "Nombre", currency: "€", date: "Date", boolean: "Oui/non" };

/** Largeur des colonnes (px) : étroites pour les dates et montants, le texte se partage le reste (200 px au moins). */
const WIDTHS: Record<ColumnType, number | null> = { date: 118, currency: 120, number: 110, boolean: 104, text: null };
const TEXT_MIN = 200;
const INDEX_WIDTH = 52;

interface Props {
  columns: Column[];
  rows: Record<string, CellValue>[];
  total: number;
  busy: boolean;
  /** Cellules corrigées : « ligne:clé » → valeur lue dans le fichier. */
  edited?: Record<string, CellValue>;
  onColumns: (columns: Column[]) => void;
  /** Enregistre des corrections ; `false` si le serveur les a refusées (la saisie reste ouverte). */
  onCells?: (edits: CellEdit[]) => Promise<boolean>;
  onMore: (() => void) | null;
}

interface Pos {
  r: number;
  c: number;
}

interface Editing extends Pos {
  draft: string;
  /** Saisie commencée en tapant un caractère : le texte n'est pas sélectionné. */
  typed: boolean;
}

/** Débit ↔ crédit d'une ligne de relevé ; null si la ligne n'a ni l'un ni l'autre (ou les deux). */
export function swapEdits(row: Record<string, CellValue>, index: number, columns: Column[]): CellEdit[] | null {
  const debit = columns.find((c) => c.role === "debit");
  const credit = columns.find((c) => c.role === "credit");
  if (!debit || !credit) return null;
  const d = row[debit.key] ?? null;
  const c = row[credit.key] ?? null;
  if ((typeof d === "number") === (typeof c === "number")) return null;
  return [
    { row: index, key: debit.key, value: c },
    { row: index, key: credit.key, value: d },
  ];
}

/**
 * Aperçu de la table : en-têtes modifiables (inclure, renommer, type, déplacer), cellules mises en forme et corrigeables.
 * Une valeur qui n'a pas pu être convertie dans le type de sa colonne est surlignée (gardée telle quelle) ; une cellule
 * corrigée porte un coin de la couleur signature, avec la valeur lue dans le fichier en info-bulle.
 * Clavier : flèches pour se déplacer, Entrée / F2 ou une lettre pour corriger, Échap pour annuler, Tab pour la suivante.
 */
export function PreviewTable({ columns, rows, total, busy, edited = {}, onColumns, onCells, onMore }: Props) {
  const tableRef = useRef<HTMLTableElement>(null);
  const [focus, setFocus] = useState<Pos>({ r: 0, c: 0 });
  const [editing, setEditingState] = useState<Editing | null>(null);
  const [saving, setSaving] = useState(false);
  const [within, setWithin] = useState(false);
  /** Saisie en cours, lue par `commit` : un `blur` tardif (après Entrée) ne renvoie pas la même correction. */
  const editingRef = useRef<Editing | null>(null);
  const savingRef = useRef(false);
  const setEditing = (value: Editing | null) => {
    editingRef.current = value;
    setEditingState(value);
  };

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
  const corrections = Object.keys(edited).length;
  const editable = Boolean(onCells) && !busy;
  const focusedRow = rows[focus.r];
  const focusedSwap = within && editable && focusedRow ? swapEdits(focusedRow, focus.r, columns) : null;

  const focusCell = (pos: Pos) => {
    const r = Math.max(0, Math.min(rows.length - 1, pos.r));
    const c = Math.max(0, Math.min(columns.length - 1, pos.c));
    setFocus({ r, c });
    tableRef.current?.querySelector<HTMLElement>(`[data-cell="${r}:${c}"]`)?.focus();
  };

  const startEdit = (pos: Pos, typed?: string) => {
    const col = columns[pos.c];
    const row = rows[pos.r];
    if (!editable || !col || !row) return;
    setFocus(pos);
    setEditing({ ...pos, draft: typed ?? editText(row[col.key] ?? null, col.type), typed: typed !== undefined });
  };

  /** Enregistre la saisie ; `next` : cellule à atteindre ensuite (Entrée, Tab), sinon la saisie se ferme sur place. */
  const commit = async (next: Pos | null) => {
    const current = editingRef.current;
    if (!current || savingRef.current || !onCells) return;
    const col = columns[current.c];
    const row = rows[current.r];
    if (!col || !row) return setEditing(null);
    if (current.draft !== editText(row[col.key] ?? null, col.type)) {
      savingRef.current = true;
      setSaving(true);
      const ok = await onCells([{ row: current.r, key: col.key, value: current.draft.trim() === "" ? null : current.draft }]);
      savingRef.current = false;
      setSaving(false);
      if (!ok) return; // la saisie reste ouverte pour être corrigée
    }
    if (editingRef.current !== current) return;
    setEditing(null);
    if (next) focusCell(next);
  };

  const cancel = () => {
    if (!editing) return;
    const pos = { r: editing.r, c: editing.c };
    setEditing(null);
    focusCell(pos);
  };

  const onCellKey = (e: KeyboardEvent<HTMLTableCellElement>, pos: Pos) => {
    const moves: Record<string, Pos> = {
      ArrowUp: { r: pos.r - 1, c: pos.c },
      ArrowDown: { r: pos.r + 1, c: pos.c },
      ArrowLeft: { r: pos.r, c: pos.c - 1 },
      ArrowRight: { r: pos.r, c: pos.c + 1 },
      Home: { r: pos.r, c: 0 },
      End: { r: pos.r, c: columns.length - 1 },
    };
    const target = moves[e.key];
    if (target) {
      e.preventDefault();
      focusCell(target);
    } else if (e.key === "Enter" || e.key === "F2") {
      e.preventDefault();
      startEdit(pos);
    } else if ((e.key === "Backspace" || e.key === "Delete") && editable) {
      e.preventDefault();
      startEdit(pos, "");
    } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey && editable) {
      e.preventDefault();
      startEdit(pos, e.key);
    }
  };

  const onEditorKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!editing) return;
    if (e.key === "Enter") {
      e.preventDefault();
      void commit({ r: editing.r + (e.shiftKey ? -1 : 1), c: editing.c });
    } else if (e.key === "Tab") {
      e.preventDefault();
      void commit({ r: editing.r, c: editing.c + (e.shiftKey ? -1 : 1) });
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancel();
    }
  };

  const swap = async (edits: CellEdit[] | null, pos: Pos) => {
    if (!edits || !onCells || busy) return;
    setSaving(true);
    await onCells(edits);
    setSaving(false);
    focusCell(pos);
  };

  return (
    <section
      aria-label="Aperçu de la table"
      onFocus={() => setWithin(true)}
      onBlur={(e) => !e.currentTarget.contains(e.relatedTarget as Node | null) && setWithin(false)}
      className="atelier-card flex min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-surface">
      <div className="min-h-0 flex-1 overflow-auto">
        <table ref={tableRef} className="convert-table table-fixed border-collapse text-sm" style={{ width: `max(100%, ${minWidth}px)` }}>
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
            {rows.map((row, r) => {
              const rowSwap = editable ? swapEdits(row, r, columns) : null;
              const toCredit = typeof rowSwap?.[1]?.value === "number";
              return (
                <tr key={r} className="group hover:bg-accent-faint">
                  <td className="relative border-b border-line px-2 py-1.5 text-right text-[11px] text-muted tabular-nums">
                    <span className={clsx(rowSwap && "group-hover:invisible")}>{r + 1}</span>
                    {rowSwap && (
                      <button
                        type="button"
                        tabIndex={-1}
                        disabled={saving}
                        onClick={() => void swap(rowSwap, { r, c: focus.c })}
                        title={toCredit ? "Passer en crédit (entrée d'argent)" : "Passer en débit (sortie d'argent)"}
                        aria-label={`Ligne ${r + 1} : ${toCredit ? "passer en crédit" : "passer en débit"}`}
                        className="absolute inset-0 m-auto hidden size-6 items-center justify-center rounded text-accent-ink group-hover:flex hover:bg-accent-soft"
                      >
                        <ArrowLeftRight className="size-3.5" aria-hidden />
                      </button>
                    )}
                  </td>
                  {columns.map((col, c) => {
                    const value = row[col.key] ?? null;
                    const bad = unconverted(value, col.type);
                    const ref = cellRef(r, col.key);
                    const wasEdited = ref in edited;
                    const isEditing = editing?.r === r && editing.c === c;
                    const shown = formatCell(value, col.type);
                    const title = bad
                      ? `Valeur gardée telle quelle : ce n'est pas un ${TYPE_LABELS[col.type].toLowerCase()}`
                      : wasEdited
                        ? `Corrigé — lu dans le fichier : ${formatCell(edited[ref] ?? null, col.type) || "(vide)"}`
                        : col.type === "text" && shown.length > 24
                          ? shown
                          : undefined;
                    return (
                      <td
                        key={col.key}
                        data-cell={`${r}:${c}`}
                        tabIndex={focus.r === r && focus.c === c && !isEditing ? 0 : -1}
                        title={isEditing ? undefined : title}
                        onFocus={() => setFocus({ r, c })}
                        onDoubleClick={() => startEdit({ r, c })}
                        onKeyDown={isEditing ? undefined : (e) => onCellKey(e, { r, c })}
                        aria-label={isEditing ? undefined : `${col.label}, ligne ${r + 1} : ${shown || "vide"}${wasEdited ? " (corrigé)" : ""}`}
                        className={clsx(
                          "truncate border-b border-l border-line px-2 py-1.5",
                          (col.type === "number" || col.type === "currency") && "num",
                          col.type === "currency" && typeof value === "number" && value < 0 && "text-negative",
                          !col.include && "text-muted opacity-50",
                          bad && "bg-warning/15 text-warning",
                          wasEdited && "cell-edited",
                          isEditing && "cell-editing",
                        )}
                      >
                        {isEditing ? (
                          <input
                            autoFocus
                            value={editing.draft}
                            readOnly={saving}
                            onChange={(e) => setEditing({ ...editing, draft: e.target.value })}
                            onFocus={(e) => !editing.typed && e.currentTarget.select()}
                            onKeyDown={onEditorKey}
                            onBlur={() => void commit(null)}
                            aria-label={`Corriger ${col.label}, ligne ${r + 1}`}
                            inputMode={col.type === "number" || col.type === "currency" ? "decimal" : undefined}
                            placeholder={col.type === "date" ? "JJ/MM/AAAA" : undefined}
                          />
                        ) : (
                          shown
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
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
          {corrections > 0 && <span className="text-accent-ink"> · {corrections} cellule(s) corrigée(s)</span>}
          {problems > 0 && <span className="text-warning"> · {problems} valeur(s) non converties (surlignées)</span>}
          {onCells && rows.length > 0 && <span className="hidden lg:inline"> · double-clic ou Entrée pour corriger une cellule</span>}
        </span>
        <span className="flex items-center gap-2">
          {focusedSwap && (
            <button
              type="button"
              disabled={saving}
              onClick={() => void swap(focusedSwap, focus)}
              className="flex items-center gap-1 rounded-md border border-border px-2 py-1 hover:bg-surface-2 hover:text-fg disabled:opacity-50"
            >
              <ArrowLeftRight className="size-3" aria-hidden />
              Ligne {focus.r + 1} : {typeof focusedSwap[1]?.value === "number" ? "passer en crédit" : "passer en débit"}
            </button>
          )}
          {onMore && (
            <button type="button" onClick={onMore} className="rounded-md border border-border px-2 py-1 hover:bg-surface-2 hover:text-fg">
              Afficher plus de lignes
            </button>
          )}
        </span>
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
